"""Image Robot API endpoints

Exposes the Image Robot Crew functionality via REST API for:
- Generating images for articles
- Uploading single images with optimization
- Checking Bunny Optimizer status
- Viewing generation history

IMPORTANT: Uses lazy imports for heavy dependencies.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime
import time
import json
import re
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from api.models.images import (
    GenerateImagesRequest,
    GenerateImagesResponse,
    GeneratedImageResponse,
    UploadImageRequest,
    UploadImageResponse,
    OptimizerStatusResponse,
    ImageRobotHistoryResponse,
    ImageRobotHistoryItem,
    ImageProfileData,
    CreateImageProfileRequest,
    ListImageProfilesResponse,
    GenerateImageFromProfileRequest,
    GenerateImageFromProfileResponse,
)
from api.dependencies.auth import require_current_user
from api.dependencies import get_image_pipeline
from api.services.ai_image_generation import generate_openai_image_to_file
from api.services.image_profiles import ImageProfileStore
from agents.seo.config.project_store import project_store

# Type hint only - not loaded at runtime
if TYPE_CHECKING:
    from agents.images.image_crew import ImagePipeline

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/images",
    tags=["Image Robot"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user)],
)


def get_current_user_id() -> str:
    """Get current user id (placeholder until auth integration)."""
    return "default-user"


def _sanitize_project_id(project_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", project_id).strip("-")
    return safe or "unknown-project"


async def _get_project_scoped_data_dir(
    crew: "ImagePipeline",
    project_id: str,
) -> Path:
    """Resolve and ensure per-project image data directory."""
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")

    # Validate project ownership when DB is configured.
    try:
        project = await project_store.get_by_id(project_id)
    except RuntimeError:
        project = None
    except Exception as e:
        logger.warning(f"Project validation skipped due to lookup error: {e}")
        project = None

    if project_store.db_client:
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        if project.user_id != get_current_user_id():
            raise HTTPException(status_code=403, detail="Project access denied")

    project_dir = Path(crew.data_dir) / "projects" / _sanitize_project_id(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def _append_history_item(history_file: Path, item: Dict[str, Any]) -> None:
    """Append one item to workflow history JSON."""
    history: list[Dict[str, Any]] = []
    if history_file.exists():
        try:
            with open(history_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list):
                history = data
        except Exception:
            history = []

    history.append(item)
    # Keep a bounded file size.
    if len(history) > 1000:
        history = history[-1000:]

    with open(history_file, "w", encoding="utf-8") as handle:
        json.dump(history, handle, indent=2, ensure_ascii=True)


def _sanitize_filename(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not normalized:
        return "image"
    return normalized[:120]


def _ensure_extension(file_name: str, image_format: str = "jpg") -> str:
    if "." in Path(file_name).name:
        return file_name
    safe_ext = image_format.lower() if image_format else "jpg"
    if safe_ext not in {"jpg", "jpeg", "png", "webp", "avif"}:
        safe_ext = "jpg"
    return f"{file_name}.{safe_ext}"


def _build_profile_file_name(
    profile_id: str,
    title_text: str,
    image_format: str = "jpg",
) -> str:
    ts = int(time.time())
    base = f"{_sanitize_filename(profile_id)}-{_sanitize_filename(title_text)}-{ts}"
    return _ensure_extension(base[:180], image_format=image_format)


def _map_optimizer_image_type(image_type: str) -> str:
    mapping = {
        "hero_image": "hero",
        "section_image": "section",
        "thumbnail": "thumbnail",
        "og_card": "hero",
    }
    return mapping.get(image_type, "hero")


def _build_ai_prompt(
    profile: Dict[str, Any],
    title_text: str,
    subtitle_text: Optional[str] = None,
    custom_prompt: Optional[str] = None,
) -> str:
    """Build a visual prompt for AI image providers."""
    if custom_prompt:
        return custom_prompt.strip()

    parts: list[str] = []
    base_prompt = (profile.get("base_prompt") or "").strip()
    if base_prompt:
        parts.append(base_prompt)

    parts.append(f"Main subject/text concept: {title_text.strip()}")
    if subtitle_text:
        parts.append(f"Secondary concept: {subtitle_text.strip()}")

    tags = profile.get("tags") or []
    if tags:
        parts.append(f"Keywords: {', '.join(str(t) for t in tags)}")

    image_type = profile.get("image_type", "hero_image")
    if image_type == "og_card":
        parts.append("Composition: social card style, strong readability, clean hierarchy.")
    elif image_type == "thumbnail":
        parts.append("Composition: bold thumbnail style with high contrast and clear focal point.")
    elif image_type == "section_image":
        parts.append("Composition: supportive editorial section illustration.")
    else:
        parts.append("Composition: hero image style, editorial quality.")

    return " ".join(parts)


@router.post(
    "/generate",
    response_model=GenerateImagesResponse,
    summary="Generate images for article",
    description="""
    Generate optimized images for a blog article using the Image Robot Crew.

    **What it does:**
    - Analyzes article content to determine visual strategy
    - Generates images via Robolly API
    - Uploads to Bunny CDN with optional Optimizer URLs
    - Returns markdown with images inserted

    **Strategy types:**
    - `minimal`: Hero image only (fastest)
    - `standard`: Hero + OG card (default)
    - `hero+sections`: Hero + section images
    - `rich`: All image types including thumbnails

    **Returns:**
    - Generated image URLs with responsive variants
    - Updated markdown with images inserted
    - OG image URL for social sharing
    - Processing statistics
    """
)
async def generate_images(
    request: GenerateImagesRequest,
    crew: "ImagePipeline" = Depends(get_image_pipeline)
) -> GenerateImagesResponse:
    """Generate images for an article via Image Robot Crew"""
    start_time = time.time()

    try:
        logger.info(f"Generating images for article: {request.article_title}")
        scoped_data_dir: Optional[Path] = None
        if request.project_id:
            scoped_data_dir = await _get_project_scoped_data_dir(
                crew=crew,
                project_id=request.project_id,
            )

        # Call the Image Robot Crew
        result = crew.process(
            article_content=request.article_content,
            article_title=request.article_title,
            article_slug=request.article_slug,
            strategy_type=request.strategy_type,
            style_guide=request.style_guide,
            generate_responsive=request.generate_responsive,
            path_type=request.path_type
        )

        # Convert to response format
        images = []
        for img_result in result.images:
            images.append(GeneratedImageResponse(
                success=img_result.success,
                image_type=img_result.image_type,
                primary_url=img_result.primary_cdn_url,
                responsive_urls=img_result.responsive_urls,
                alt_text=img_result.alt_text,
                file_name=img_result.file_name,
                file_size_kb=img_result.generated.file_size_kb if img_result.generated else None,
                error=img_result.errors[0] if img_result.errors else None
            ))

        processing_time_ms = int((time.time() - start_time) * 1000)

        # Persist per-project (or global) history item.
        try:
            history_dir = scoped_data_dir or Path(crew.data_dir)
            history_file = history_dir / "workflow_history.json"
            _append_history_item(
                history_file=history_file,
                item={
                    "workflow_id": f"img_{int(time.time() * 1000)}",
                    "timestamp": datetime.utcnow().isoformat(),
                    "article_title": request.article_title,
                    "article_slug": request.article_slug,
                    "total_images": result.total_images,
                    "successful_images": result.successful_images,
                    "failed_images": result.failed_images,
                    "processing_time_ms": processing_time_ms,
                    "cdn_urls_count": len(result.cdn_urls) if result.cdn_urls else 0,
                    "total_cdn_size_kb": result.total_cdn_size_kb,
                },
            )
        except Exception as history_err:
            logger.warning(f"Failed to write image history: {history_err}")

        return GenerateImagesResponse(
            success=result.successful_images > 0,
            total_images=result.total_images,
            successful_images=result.successful_images,
            failed_images=result.failed_images,
            images=images,
            markdown_with_images=result.markdown_with_images,
            og_image_url=result.og_image_url,
            total_cdn_size_kb=result.total_cdn_size_kb,
            processing_time_ms=processing_time_ms,
            strategy_used=result.strategy.strategy_type
        )

    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Image generation failed: {str(e)}"
        )


@router.post(
    "/upload",
    response_model=UploadImageResponse,
    summary="Upload single image to CDN",
    description="""
    Upload a single image to Bunny CDN with optimization.

    **What it does:**
    - Downloads image from source URL
    - Uploads to Bunny CDN storage
    - Generates Optimizer URLs for responsive variants

    **Returns:**
    - CDN URL of uploaded image
    - Optimizer URL with transformation params
    - Responsive variant URLs
    """
)
async def upload_image(
    request: UploadImageRequest,
    crew: "ImagePipeline" = Depends(get_image_pipeline)
) -> UploadImageResponse:
    """Upload a single image with optimization"""
    try:
        logger.info(f"Uploading image: {request.file_name}")

        # Use CDN Manager directly for single uploads
        cdn_manager = crew.cdn_manager

        result = cdn_manager.upload_with_optimizer(
            source=str(request.source_url),
            file_name=request.file_name,
            alt_text=request.alt_text,
            image_type=request.image_type,
            path_type=request.path_type
        )

        if not result.get("success"):
            return UploadImageResponse(
                success=False,
                error=result.get("error", "Upload failed")
            )

        return UploadImageResponse(
            success=True,
            cdn_url=result.get("cdn_url"),
            optimizer_url=result.get("optimizer_url"),
            responsive_urls=result.get("responsive_urls", {}),
            file_size_kb=result.get("file_size_kb"),
            content_type=result.get("content_type"),
            storage_path=result.get("storage_path")
        )

    except Exception as e:
        logger.error(f"Image upload failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Image upload failed: {str(e)}"
        )


@router.get(
    "/optimizer/status",
    response_model=OptimizerStatusResponse,
    summary="Check Bunny Optimizer status",
    description="""
    Check the status of Bunny CDN Optimizer.

    **What it checks:**
    - Whether optimizer is enabled in config
    - CDN hostname configuration
    - Optionally verifies transformation works

    **Returns:**
    - Enabled status
    - Hostname and configuration
    - Verification result if test URL provided
    """
)
async def get_optimizer_status(
    test_url: str = None,
    crew: "ImagePipeline" = Depends(get_image_pipeline)
) -> OptimizerStatusResponse:
    """Check Bunny Optimizer configuration and status"""
    try:
        from agents.images.config.image_config import BUNNY_CONFIG

        optimizer_config = BUNNY_CONFIG.get("optimizer", {})
        enabled = optimizer_config.get("enabled", False)
        hostname = BUNNY_CONFIG.get("storage", {}).get("hostname", "")

        # Base response
        response = OptimizerStatusResponse(
            enabled=enabled,
            config_enabled=enabled,
            hostname=hostname if hostname else None,
            message="Bunny Optimizer is " + ("enabled" if enabled else "disabled"),
            supported_formats=optimizer_config.get("formats", ["webp", "avif", "jpeg", "png"]),
            default_quality=optimizer_config.get("default_quality", 85)
        )

        # Optionally verify with a test URL
        if test_url and enabled and hostname:
            try:
                from agents.images.tools.bunny_optimizer_tools import generate_optimized_url

                transformed_result = generate_optimized_url(
                    base_url=test_url,
                    width=800,
                    quality=85,
                    format="webp"
                )
                transformed = transformed_result.get("url", test_url)
                response.verified = True
                response.test_url = test_url
                response.transformed_url = transformed
                response.message = "Bunny Optimizer is enabled and verified"
            except Exception as e:
                response.verified = False
                response.message = f"Bunny Optimizer enabled but verification failed: {e}"

        return response

    except Exception as e:
        logger.error(f"Optimizer status check failed: {e}")
        return OptimizerStatusResponse(
            enabled=False,
            config_enabled=False,
            message=f"Failed to check optimizer status: {str(e)}"
        )


@router.get(
    "/history",
    response_model=ImageRobotHistoryResponse,
    summary="Get generation history",
    description="""
    Get recent image generation history.

    **Returns:**
    - List of recent generation jobs
    - Statistics for each job
    """
)
async def get_generation_history(
    limit: int = 20,
    project_id: Optional[str] = Query(
        default=None,
        description="Optional project id for project-scoped history",
    ),
    crew: "ImagePipeline" = Depends(get_image_pipeline)
) -> ImageRobotHistoryResponse:
    """Get recent image generation history"""
    try:
        if project_id:
            scoped_dir = await _get_project_scoped_data_dir(
                crew=crew,
                project_id=project_id,
            )
            history_file = scoped_dir / "workflow_history.json"
        else:
            history_file = Path(crew.data_dir) / "workflow_history.json"

        if not history_file.exists():
            return ImageRobotHistoryResponse(items=[], total_count=0)

        with open(history_file, 'r') as f:
            history = json.load(f)

        # Get most recent items
        items = [
            ImageRobotHistoryItem(**item)
            for item in history[-limit:]
        ]
        items.reverse()  # Most recent first

        return ImageRobotHistoryResponse(
            items=items,
            total_count=len(history)
        )

    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        return ImageRobotHistoryResponse(items=[], total_count=0)


@router.get(
    "/profiles",
    response_model=ListImageProfilesResponse,
    summary="List image generation profiles",
    description="""
    Return system and custom profiles for image generation.

    These profiles define defaults for:
    - Image type (hero, OG, section, thumbnail)
    - Style guide
    - CDN path
    - Optional template overrides
    """
)
async def list_image_profiles(
    project_id: str = Query(
        ...,
        description="Project id used to scope image profiles",
    ),
    crew: "ImagePipeline" = Depends(get_image_pipeline)
) -> ListImageProfilesResponse:
    """List available image profiles (system + custom)."""
    try:
        scoped_dir = await _get_project_scoped_data_dir(
            crew=crew,
            project_id=project_id,
        )
        store = ImageProfileStore(scoped_dir)
        items = [ImageProfileData(**profile) for profile in store.list_profiles()]
        return ListImageProfilesResponse(items=items, total_count=len(items))
    except Exception as e:
        logger.error(f"Failed to list image profiles: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list profiles: {str(e)}")


@router.post(
    "/profiles",
    response_model=ImageProfileData,
    summary="Create or update custom image profile",
    description="""
    Create or update a custom generation profile.

    Notes:
    - System profiles cannot be overwritten.
    - Custom profiles are persisted in `data/images/projects/{project_id}/image_profiles.json`.
    """
)
async def upsert_image_profile(
    request: CreateImageProfileRequest,
    project_id: str = Query(
        ...,
        description="Project id used to scope image profiles",
    ),
    crew: "ImagePipeline" = Depends(get_image_pipeline)
) -> ImageProfileData:
    """Create or update a custom profile."""
    try:
        scoped_dir = await _get_project_scoped_data_dir(
            crew=crew,
            project_id=project_id,
        )
        store = ImageProfileStore(scoped_dir)
        saved = store.save_custom_profile(request.dict())
        return ImageProfileData(**saved)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save image profile: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save profile: {str(e)}")


@router.delete(
    "/profiles/{profile_id}",
    summary="Delete custom image profile",
    description="""
    Delete a custom profile by id.

    Notes:
    - System profiles cannot be deleted.
    """
)
async def delete_image_profile(
    profile_id: str,
    project_id: str = Query(
        ...,
        description="Project id used to scope image profiles",
    ),
    crew: "ImagePipeline" = Depends(get_image_pipeline)
) -> Dict[str, Any]:
    """Delete a custom profile."""
    try:
        scoped_dir = await _get_project_scoped_data_dir(
            crew=crew,
            project_id=project_id,
        )
        store = ImageProfileStore(scoped_dir)
        deleted = store.delete_custom_profile(profile_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Profile not found")
        return {"success": True, "profile_id": profile_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/generate-from-profile",
    response_model=GenerateImageFromProfileResponse,
    summary="Generate image on-the-fly from profile",
    description="""
    Generate one image immediately from a pre-registered profile.

	    Workflow:
	    1. Resolve profile defaults (type/style/path/template)
	    2. Generate image via resolved provider (Robolly or OpenAI)
	    3. Upload original to Bunny CDN
	    4. Return optimizer-based responsive URLs
	    """
)
async def generate_image_from_profile(
    request: GenerateImageFromProfileRequest,
    crew: "ImagePipeline" = Depends(get_image_pipeline)
) -> GenerateImageFromProfileResponse:
    """Generate one image from a saved profile."""
    try:
        scoped_dir = await _get_project_scoped_data_dir(
            crew=crew,
            project_id=request.project_id,
        )
        store = ImageProfileStore(scoped_dir)
        profile = store.get_profile(request.profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        resolved_style = request.style_guide_override or profile.get("style_guide", "brand_primary")
        resolved_path = request.path_type_override or profile.get("path_type", "articles")
        resolved_template = request.template_id_override or profile.get("template_id")
        resolved_provider = request.provider_override or profile.get("image_provider", "robolly")
        image_type = profile.get("image_type", "hero_image")
        prompt_used: Optional[str] = None
        temp_local_path: Optional[str] = None

        if resolved_provider == "robolly":
            from agents.images.schemas.image_schemas import ImageBrief, ImageType

            brief = ImageBrief(
                image_type=ImageType(image_type),
                title_text=request.title_text,
                subtitle_text=request.subtitle_text,
                template_id=resolved_template,
                context_keywords=profile.get("tags", []),
            )

            generation_result = crew.generator.generate_from_brief(
                brief=brief,
                style_guide=resolved_style,
            )

            if not generation_result.get("success"):
                return GenerateImageFromProfileResponse(
                    success=False,
                    profile=ImageProfileData(**profile),
                    image_type=image_type,
                    provider_used=resolved_provider,
                    style_guide_used=resolved_style,
                    path_type_used=resolved_path,
                    error=generation_result.get("error", "Generation failed"),
                )

            generated = generation_result.get("generated", {})
            source_url = generated.get("original_url")
            if not source_url:
                return GenerateImageFromProfileResponse(
                    success=False,
                    profile=ImageProfileData(**profile),
                    image_type=image_type,
                    provider_used=resolved_provider,
                    style_guide_used=resolved_style,
                    path_type_used=resolved_path,
                    error="Generated image URL missing",
                )
        elif resolved_provider == "openai":
            prompt_used = _build_ai_prompt(
                profile=profile,
                title_text=request.title_text,
                subtitle_text=request.subtitle_text,
                custom_prompt=request.custom_prompt,
            )
            ai_result = generate_openai_image_to_file(
                prompt=prompt_used,
                image_type=image_type,
            )
            temp_local_path = ai_result.get("local_path")
            if not temp_local_path:
                return GenerateImageFromProfileResponse(
                    success=False,
                    profile=ImageProfileData(**profile),
                    image_type=image_type,
                    provider_used=resolved_provider,
                    prompt_used=prompt_used,
                    style_guide_used=resolved_style,
                    path_type_used=resolved_path,
                    error="AI image generation returned no local file",
                )
            generation_result = {"total_time_ms": None}
            generated = {
                "original_url": temp_local_path,
                "robolly_render_id": None,
                "format": "png",
            }
            source_url = temp_local_path
        else:
            return GenerateImageFromProfileResponse(
                success=False,
                profile=ImageProfileData(**profile),
                image_type=image_type,
                provider_used=resolved_provider,
                style_guide_used=resolved_style,
                path_type_used=resolved_path,
                error=f"Unsupported image provider: {resolved_provider}",
            )

        image_format = generated.get("format", "jpg")
        resolved_file_name = request.file_name or _build_profile_file_name(
            profile_id=request.profile_id,
            title_text=request.title_text,
            image_format=image_format,
        )
        resolved_file_name = _ensure_extension(resolved_file_name, image_format=image_format)

        resolved_alt_text = (
            request.alt_text
            or profile.get("default_alt_text")
            or f"{profile.get('name', 'Image')} - {request.title_text}"
        )

        upload_result = crew.cdn_manager.upload_with_optimizer(
            source=source_url,
            file_name=resolved_file_name,
            alt_text=resolved_alt_text,
            path_type=resolved_path,
            image_type=_map_optimizer_image_type(image_type),
        )

        if not upload_result.get("success"):
            return GenerateImageFromProfileResponse(
                success=False,
                profile=ImageProfileData(**profile),
                image_type=image_type,
                source_image_url=source_url,
                render_id=generated.get("robolly_render_id"),
                file_name=resolved_file_name,
                alt_text=resolved_alt_text,
                provider_used=resolved_provider,
                prompt_used=prompt_used,
                style_guide_used=resolved_style,
                path_type_used=resolved_path,
                generation_time_ms=generation_result.get("total_time_ms"),
                error=upload_result.get("error", "Upload failed"),
            )

        responsive_urls = {
            str(k): v for k, v in upload_result.get("responsive_urls", {}).items()
        }

        return GenerateImageFromProfileResponse(
            success=True,
            profile=ImageProfileData(**profile),
            image_type=image_type,
            source_image_url=source_url,
            cdn_url=upload_result.get("cdn_url"),
            primary_url=upload_result.get("primary_url"),
            responsive_urls=responsive_urls,
            render_id=generated.get("robolly_render_id"),
            file_name=resolved_file_name,
            alt_text=resolved_alt_text,
            provider_used=resolved_provider,
            prompt_used=prompt_used,
            style_guide_used=resolved_style,
            path_type_used=resolved_path,
            storage_path=upload_result.get("storage_path"),
            generation_time_ms=generation_result.get("total_time_ms"),
            upload_time_ms=upload_result.get("upload_time_ms"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Profile generation failed: {str(e)}")
    finally:
        # Best-effort cleanup for temporary AI files.
        try:
            if "temp_local_path" in locals() and temp_local_path:
                path = Path(temp_local_path)
                if path.exists():
                    path.unlink()
        except Exception:
            pass


@router.post(
    "/quick-generate",
    response_model=GenerateImagesResponse,
    summary="Quick generate hero image only",
    description="""
    Fast image generation with hero image only.

    This is a convenience endpoint for quick generation
    without responsive variants. Good for previews.
    """
)
async def quick_generate_images(
    request: GenerateImagesRequest,
    crew: "ImagePipeline" = Depends(get_image_pipeline)
) -> GenerateImagesResponse:
    """Quick image generation (hero only, no responsive)"""
    start_time = time.time()

    try:
        logger.info(f"Quick generating image for: {request.article_title}")
        scoped_data_dir: Optional[Path] = None
        if request.project_id:
            scoped_data_dir = await _get_project_scoped_data_dir(
                crew=crew,
                project_id=request.project_id,
            )

        result = crew.quick_process(
            article_content=request.article_content,
            article_title=request.article_title,
            article_slug=request.article_slug,
            hero_only=True
        )

        images = []
        for img_result in result.images:
            images.append(GeneratedImageResponse(
                success=img_result.success,
                image_type=img_result.image_type,
                primary_url=img_result.primary_cdn_url,
                responsive_urls=img_result.responsive_urls,
                alt_text=img_result.alt_text,
                file_name=img_result.file_name,
                error=img_result.errors[0] if img_result.errors else None
            ))

        processing_time_ms = int((time.time() - start_time) * 1000)

        try:
            history_dir = scoped_data_dir or Path(crew.data_dir)
            history_file = history_dir / "workflow_history.json"
            _append_history_item(
                history_file=history_file,
                item={
                    "workflow_id": f"img_{int(time.time() * 1000)}",
                    "timestamp": datetime.utcnow().isoformat(),
                    "article_title": request.article_title,
                    "article_slug": request.article_slug,
                    "total_images": result.total_images,
                    "successful_images": result.successful_images,
                    "failed_images": result.failed_images,
                    "processing_time_ms": processing_time_ms,
                    "cdn_urls_count": len(result.cdn_urls) if result.cdn_urls else 0,
                    "total_cdn_size_kb": result.total_cdn_size_kb,
                },
            )
        except Exception as history_err:
            logger.warning(f"Failed to write quick image history: {history_err}")

        return GenerateImagesResponse(
            success=result.successful_images > 0,
            total_images=result.total_images,
            successful_images=result.successful_images,
            failed_images=result.failed_images,
            images=images,
            markdown_with_images=result.markdown_with_images,
            og_image_url=result.og_image_url,
            total_cdn_size_kb=result.total_cdn_size_kb,
            processing_time_ms=processing_time_ms,
            strategy_used="minimal"
        )

    except Exception as e:
        logger.error(f"Quick image generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Quick image generation failed: {str(e)}"
        )
