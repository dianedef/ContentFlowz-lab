"""Psychology Engine API Router

Exposes CrewAI agents for narrative synthesis, persona refinement,
and content angle generation. Uses background tasks for long-running
agent operations with polling-based status retrieval.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from api.dependencies.auth import CurrentUser, require_current_user
from api.services.job_store import job_store
from api.services.ai_runtime_service import AIRuntimeServiceError, ai_runtime_service
from api.services.user_llm_service import (
    DEFAULT_OPENROUTER_MODEL,
    NEWSLETTER_OPENROUTER_MODEL,
    AIRuntimeResolutionError,
    UserLLMCredentialError,
    user_llm_service,
)
from status.audit import actor_from_agent
from api.models.psychology import (
    NarrativeSynthesisRequest,
    NarrativeSynthesisResult,
    PersonaRefinementRequest,
    AngleGenerationRequest,
    ContentAngleResult,
    AngleSelectionInput,
    MultiFormatExtract,
    PipelineDispatchRequest,
    PipelineDispatchResult,
)
import json
import uuid

router = APIRouter(prefix="/api/psychology", tags=["Psychology Engine"])


def _raise_runtime_http(exc: Exception) -> None:
    if isinstance(exc, AIRuntimeServiceError):
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    if isinstance(exc, AIRuntimeResolutionError):
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    raise HTTPException(status_code=409, detail=str(exc)) from exc


async def _create_job(task_id: str, job_type: str, user_id: str, message: str) -> None:
    await job_store.upsert(
        job_id=task_id,
        job_type=job_type,
        status="running",
        progress=5,
        message=message,
        user_id=user_id,
        result=None,
        error=None,
    )


async def _get_owned_job(task_id: str, user_id: str) -> dict:
    job = await job_store.get(task_id)
    if not job or job.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return job


# ─────────────────────────────────────────────────
# Narrative Synthesis (Creator Brain)
# ─────────────────────────────────────────────────

async def _run_synthesis_task(
    task_id: str,
    user_id: str,
    request: NarrativeSynthesisRequest,
):
    """Background task: run Creator Psychologist agent"""
    try:
        from agents.psychology.creator_psychologist import run_narrative_synthesis

        llm = await user_llm_service.get_crewai_llm(
            user_id,
            model=DEFAULT_OPENROUTER_MODEL,
            route="psychology.synthesize_narrative",
        )
        result = run_narrative_synthesis(
            profile_id=request.profile_id,
            entries=request.to_entry_payloads(),
            current_voice=request.current_voice,
            current_positioning=request.current_positioning,
            chapter_title=request.chapter_title,
            llm=llm,
        )
        await job_store.update(
            task_id,
            status="completed",
            progress=100,
            message="Narrative synthesis completed.",
            result=result,
            error=None,
        )
    except Exception as e:
        await job_store.update(
            task_id,
            status="failed",
            progress=100,
            message="Narrative synthesis failed.",
            error=str(e),
        )


@router.post("/synthesize-narrative")
async def synthesize_narrative(
    request: NarrativeSynthesisRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_current_user),
):
    """Trigger narrative synthesis from creator entries (async)."""
    try:
        await user_llm_service.get_openrouter_key(
            current_user.user_id,
            route="psychology.synthesize_narrative",
        )
    except UserLLMCredentialError as exc:
        _raise_runtime_http(exc)

    task_id = str(uuid.uuid4())
    await _create_job(
        task_id,
        "psychology.synthesize_narrative",
        current_user.user_id,
        "Narrative synthesis started.",
    )
    background_tasks.add_task(_run_synthesis_task, task_id, current_user.user_id, request)
    return {"task_id": task_id, "status": "running"}


@router.get("/synthesis-status/{task_id}")
async def get_synthesis_status(
    task_id: str,
    current_user: CurrentUser = Depends(require_current_user),
):
    """Poll for narrative synthesis result."""
    return await _get_owned_job(task_id, current_user.user_id)


# ─────────────────────────────────────────────────
# Persona Refinement (Customer Brain)
# ─────────────────────────────────────────────────

async def _run_refinement_task(
    task_id: str,
    user_id: str,
    request: PersonaRefinementRequest,
):
    """Background task: run Audience Analyst agent"""
    try:
        from agents.psychology.audience_analyst import run_persona_refinement

        llm = await user_llm_service.get_crewai_llm(
            user_id,
            model=DEFAULT_OPENROUTER_MODEL,
            route="psychology.refine_persona",
        )
        result = run_persona_refinement(
            persona=request.current_persona.to_canonical_dict(),
            analytics_data=request.analytics_data,
            content_performance=request.content_performance,
            llm=llm,
        )
        await job_store.update(
            task_id,
            status="completed",
            progress=100,
            message="Persona refinement completed.",
            result=result,
            error=None,
        )
    except Exception as e:
        await job_store.update(
            task_id,
            status="failed",
            progress=100,
            message="Persona refinement failed.",
            error=str(e),
        )


@router.post("/refine-persona")
async def refine_persona(
    request: PersonaRefinementRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_current_user),
):
    """Trigger persona refinement using analytics data (async)."""
    try:
        await user_llm_service.get_openrouter_key(
            current_user.user_id,
            route="psychology.refine_persona",
        )
    except UserLLMCredentialError as exc:
        _raise_runtime_http(exc)

    task_id = str(uuid.uuid4())
    await _create_job(
        task_id,
        "psychology.refine_persona",
        current_user.user_id,
        "Persona refinement started.",
    )
    background_tasks.add_task(_run_refinement_task, task_id, current_user.user_id, request)
    return {"task_id": task_id, "status": "running"}


@router.get("/refinement-status/{task_id}")
async def get_refinement_status(
    task_id: str,
    current_user: CurrentUser = Depends(require_current_user),
):
    """Poll for persona refinement result."""
    return await _get_owned_job(task_id, current_user.user_id)


# ─────────────────────────────────────────────────
# Angle Generation (The Bridge)
# ─────────────────────────────────────────────────

async def _run_angle_task(
    task_id: str,
    user_id: str,
    request: AngleGenerationRequest,
):
    """Background task: run Angle Strategist agent"""
    try:
        from agents.psychology.angle_strategist import run_angle_generation

        llm = await user_llm_service.get_crewai_llm(
            user_id,
            model=DEFAULT_OPENROUTER_MODEL,
            route="psychology.generate_angles",
        )
        result = run_angle_generation(
            creator_voice=request.creator_voice,
            creator_positioning=request.creator_positioning,
            narrative_summary=request.narrative_summary,
            persona_data=request.persona_data.to_canonical_dict(),
            content_type=request.content_type.value if request.content_type else None,
            count=request.count,
            seo_signals=request.seo_signals,
            trending_signals=request.trending_signals,
            llm=llm,
        )
        await job_store.update(
            task_id,
            status="completed",
            progress=100,
            message="Angle generation completed.",
            result=result,
            error=None,
        )
    except Exception as e:
        await job_store.update(
            task_id,
            status="failed",
            progress=100,
            message="Angle generation failed.",
            error=str(e),
        )


@router.post("/generate-angles")
async def generate_angles(
    request: AngleGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_current_user),
):
    """Trigger content angle generation (async)."""
    try:
        await user_llm_service.get_openrouter_key(
            current_user.user_id,
            route="psychology.generate_angles",
        )
    except UserLLMCredentialError as exc:
        _raise_runtime_http(exc)

    task_id = str(uuid.uuid4())
    await _create_job(
        task_id,
        "psychology.generate_angles",
        current_user.user_id,
        "Angle generation started.",
    )
    background_tasks.add_task(_run_angle_task, task_id, current_user.user_id, request)
    return {"task_id": task_id, "status": "running"}


@router.get("/angles-status/{task_id}")
async def get_angles_status(
    task_id: str,
    current_user: CurrentUser = Depends(require_current_user),
):
    """Poll for angle generation result."""
    return await _get_owned_job(task_id, current_user.user_id)


# ─────────────────────────────────────────────────
# Multi-Format Render
# ─────────────────────────────────────────────────

@router.post("/render-extract", response_model=MultiFormatExtract, deprecated=True)
async def render_extract(
    request: AngleSelectionInput,
):
    """Deprecated — use POST /api/psychology/dispatch-pipeline instead.
    Returns static placeholder text.
    """
    return MultiFormatExtract(
        angle_id=request.angle_id,
        article_outline=f"# Article based on angle {request.angle_id}\n\n## Introduction\n...\n## Main Points\n...\n## Conclusion\n...",
        newsletter_hook=f"This week, something clicked...",
        social_post=f"Thread: Here's what I learned...",
        video_script_opener=f"Hey, today I want to share...",
    )


# ─────────────────────────────────────────────────
# Pipeline Dispatch (replaces render-extract)
# ─────────────────────────────────────────────────

# Format → (content_type, source_robot)
_FORMAT_MAP = {
    "article": ("article", "seo"),
    "newsletter": ("newsletter", "newsletter"),
    "short": ("short", "short"),
    "social_post": ("social_post", "social"),
}

_PIPELINE_ACTOR_MAP = {
    "article": "article_pipeline",
    "newsletter": "newsletter_pipeline",
    "short": "short_pipeline",
    "social_post": "social_post_pipeline",
}

_DISPATCH_ROUTE_BY_FORMAT = {
    "article": "psychology.dispatch_pipeline.article",
    "newsletter": "psychology.dispatch_pipeline.newsletter",
    "short": "psychology.dispatch_pipeline.short",
    "social_post": "psychology.dispatch_pipeline.social_post",
}

_DISPATCH_REQUIRED_PROVIDERS = {
    "article": ["openrouter", "exa"],
    "newsletter": ["openrouter", "exa"],
    "short": ["openrouter"],
    "social_post": ["openrouter"],
}

_DISPATCH_OPTIONAL_PROVIDERS = {
    "article": ["firecrawl"],
    "newsletter": [],
    "short": [],
    "social_post": [],
}


def _pipeline_actor_for_format(fmt: str):
    """Return the canonical audit actor for a supported pipeline format."""

    actor_id = _PIPELINE_ACTOR_MAP.get(fmt)
    if not actor_id:
        raise ValueError(f"Unknown pipeline actor for format '{fmt}'")
    return actor_from_agent(actor_id)


async def _run_pipeline_task(
    task_id: str,
    content_record_id: str,
    user_id: str,
    request: PipelineDispatchRequest,
):
    """Background task: dispatch to the appropriate content pipeline."""
    try:
        from status import get_status_service
        svc = get_status_service()

        fmt = request.target_format
        route_id = _DISPATCH_ROUTE_BY_FORMAT.get(fmt, "psychology.dispatch_pipeline")
        resolution = await ai_runtime_service.preflight_providers(
            user_id=user_id,
            route=route_id,
            required_providers=_DISPATCH_REQUIRED_PROVIDERS.get(fmt, ["openrouter"]),
            optional_providers=_DISPATCH_OPTIONAL_PROVIDERS.get(fmt, []),
        )
        angle = request.angle_data
        voice = request.creator_voice or {}
        body = ""
        llm_model = (
            NEWSLETTER_OPENROUTER_MODEL
            if fmt == "newsletter"
            else DEFAULT_OPENROUTER_MODEL
        )
        with ai_runtime_service.bind_provider_env(resolution):
            llm = await user_llm_service.get_crewai_llm(
                user_id,
                model=llm_model,
                route=route_id,
            )

            # Load project memory context to avoid duplicate topics
            existing_content_context = ""
            try:
                from memory.memory_service import get_memory_service
                mem = get_memory_service()
                existing_content_context = mem.load_project_context(
                    query=angle.get("title", ""),
                    user_id=user_id,
                    project_id=request.project_id,
                    limit=10,
                )
            except Exception:
                pass  # Memory service is optional

            if fmt == "article":
                from agents.seo.seo_crew import SEOContentCrew
                crew = SEOContentCrew(
                    llm_model=llm,
                    track_status=False,
                    include_firecrawl_tools=resolution.has_optional_provider("firecrawl"),
                )
                brand_voice_str = json.dumps(voice) if voice else None
                if existing_content_context and brand_voice_str:
                    brand_voice_str += f"\n\n{existing_content_context}"
                result = crew.generate_content(
                    target_keyword=request.seo_keyword or angle.get("title", ""),
                    brand_voice=brand_voice_str,
                    word_count=2500,
                )
                outputs = result.get("outputs", {})
                body = outputs.get("final_article") or outputs.get("article") or str(result)

            elif fmt == "newsletter":
                from agents.newsletter.newsletter_crew import NewsletterCrew
                from agents.newsletter.schemas.newsletter_schemas import (
                    NewsletterConfig,
                    NewsletterTone,
                )

                crew = NewsletterCrew(llm_model=llm, use_gmail=False, track_status=False)
                result = crew.generate_newsletter(
                    NewsletterConfig(
                        name=angle.get("title", "Generated newsletter"),
                        topics=[angle.get("title", "")],
                        target_audience=angle.get("pain_point_addressed", "general"),
                        tone=NewsletterTone.PROFESSIONAL,
                        include_email_insights=False,
                    ),
                    user_id=user_id,
                    project_id=request.project_id,
                )
                draft = result.get("draft", {})
                body = draft.get("plain_text") or draft.get("html_content") or str(result)

            elif fmt == "short":
                from agents.short.short_crew import ShortContentCrew
                crew = ShortContentCrew(llm_model=llm)
                result = crew.generate_short(
                    angle=angle,
                    creator_voice=voice,
                    project_id=request.project_id,
                    create_content_record=False,
                )
                body = result.get("script", str(result))

            elif fmt == "social_post":
                from agents.social.social_crew import SocialPostCrew
                crew = SocialPostCrew(llm_model=llm)
                result = crew.generate_social_post(
                    angle=angle,
                    creator_voice=voice,
                    project_id=request.project_id,
                    create_content_record=False,
                )
                posts = result.get("posts", [])
                body = json.dumps(posts, indent=2) if posts else str(result)

            else:
                raise ValueError(f"Unknown format: {fmt}")

        # Save body and transition to pending_review
        pipeline_actor = _pipeline_actor_for_format(fmt)
        if body:
            svc.save_content_body(content_record_id, body, edited_by=pipeline_actor)
        svc.transition(content_record_id, "pending_review", pipeline_actor)

        # Post-generation: mark source ideas as 'used'
        source_idea_ids = request.angle_data.get("source_idea_ids", [])
        for idea_id in source_idea_ids:
            try:
                svc.update_idea(idea_id, status="used")
            except Exception:
                pass

        # Memory integration: record generation for semantic dedup (scoped)
        try:
            from memory.memory_service import get_memory_service
            mem = get_memory_service()
            mem.store_generation_scoped(
                content_type=fmt,
                title=request.angle_data.get("title", ""),
                user_id=user_id,
                project_id=request.project_id,
                topics=request.angle_data.get("topics", []),
                summary=body[:200] if body else "",
                seo_keyword=request.seo_keyword,
                source=request.angle_data.get("source"),
            )
        except Exception:
            pass  # Memory service is optional

        await job_store.update(
            task_id,
            status="completed",
            progress=100,
            message="Pipeline content generation completed.",
            result={
                "content_record_id": content_record_id,
                "format": fmt,
                "preview": body[:500] if body else None,
            },
            error=None,
        )

    except Exception as e:
        await job_store.update(
            task_id,
            status="failed",
            progress=100,
            message="Pipeline content generation failed.",
            error=str(e),
            result={"content_record_id": content_record_id},
        )
        # Try to mark the content record as failed
        try:
            from status import get_status_service
            svc = get_status_service()
            svc.transition(
                content_record_id,
                "failed",
                _pipeline_actor_for_format(request.target_format),
                reason=str(e),
            )
        except Exception:
            pass


@router.post("/dispatch-pipeline", response_model=PipelineDispatchResult)
async def dispatch_pipeline(
    request: PipelineDispatchRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_current_user),
):
    """Dispatch an angle to a content generation pipeline (async).

    Replaces the deprecated render-extract endpoint with real content generation.
    Checks for duplicate content before creating. Creates a ContentRecord and
    launches the appropriate pipeline in the background.
    """
    fmt = request.target_format
    if fmt not in _FORMAT_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown format '{fmt}'. Valid: {list(_FORMAT_MAP.keys())}",
        )

    route_id = _DISPATCH_ROUTE_BY_FORMAT.get(fmt, "psychology.dispatch_pipeline")
    try:
        await ai_runtime_service.preflight_providers(
            user_id=current_user.user_id,
            route=route_id,
            required_providers=_DISPATCH_REQUIRED_PROVIDERS.get(fmt, ["openrouter"]),
            optional_providers=_DISPATCH_OPTIONAL_PROVIDERS.get(fmt, []),
        )
    except Exception as exc:
        _raise_runtime_http(exc)

    content_type, source_robot = _FORMAT_MAP[fmt]
    task_id = str(uuid.uuid4())
    title = request.angle_data.get("title", f"Untitled {fmt}")

    # Pre-generation dedup check
    from utils.dedup import check_content_duplicate
    duplicate = check_content_duplicate(
        title=title,
        user_id=current_user.user_id,
        project_id=request.project_id,
    )
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "content_duplicate_conflict",
                "message": "Similar content already exists.",
                "kind": "business_conflict",
                "route": "psychology.dispatch_pipeline",
                "retryable": False,
                "details": {
                    "existingContentId": duplicate["id"],
                    "existingTitle": duplicate["title"],
                    "existingStatus": duplicate["status"],
                },
            },
        )

    # Create content record
    try:
        from status import get_status_service
        svc = get_status_service()
        record = svc.create_content(
            title=title,
            content_type=content_type,
            source_robot=source_robot,
            status="in_progress",
            project_id=request.project_id,
            user_id=current_user.user_id,
            tags=[fmt],
            metadata={
                "angle": request.angle_data,
                "pipeline_task_id": task_id,
                "seo_keyword": request.seo_keyword,
                "seo_signals": request.angle_data.get("seo_signals"),
                "source_idea_ids": request.angle_data.get("source_idea_ids", []),
                "source_idea_source": request.angle_data.get("source"),
            },
        )
        content_record_id = record.id
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create content record: {e}")

    await _create_job(
        task_id,
        "psychology.dispatch_pipeline",
        current_user.user_id,
        "Pipeline content generation started.",
    )
    background_tasks.add_task(
        _run_pipeline_task,
        task_id,
        content_record_id,
        current_user.user_id,
        request,
    )

    return PipelineDispatchResult(
        task_id=task_id,
        content_record_id=content_record_id,
        format=fmt,
        status="running",
    )


@router.get("/pipeline-status/{task_id}")
async def get_pipeline_status(
    task_id: str,
    current_user: CurrentUser = Depends(require_current_user),
):
    """Poll for pipeline dispatch result."""
    return await _get_owned_job(task_id, current_user.user_id)
