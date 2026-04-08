"""
CDN Manager Agent
Uploads images to Bunny.net CDN and manages delivery
"""
from typing import Dict, Any, List, Optional
import re
import logging
from datetime import datetime

from agents.images.tools.bunny_cdn_tools import (
    upload_to_bunny_storage,
    verify_cdn_propagation,
    purge_cdn_cache,
    get_cdn_url
)
from agents.images.tools.bunny_optimizer_tools import (
    generate_optimized_url,
    generate_responsive_srcset,
    verify_optimizer_enabled
)
from agents.images.schemas.image_schemas import (
    ResponsiveImageSet,
    CDNUploadResult,
    ImageGenerationResult,
    ImageType,
    OptimizerURL,
    OptimizerImageSet
)
from agents.images.config.image_config import BUNNY_CONFIG

logger = logging.getLogger(__name__)


class CDNManager:
    """
    High-level interface for the CDN Manager agent.
    Provides methods for uploading and managing CDN content.

    Supports two modes:
    1. Optimizer mode (default): Upload original only, generate dynamic URLs
    2. Legacy mode: Upload multiple pre-generated variants
    """

    def __init__(self, llm_model: str = "gpt-4o-mini"):
        self.llm_model = llm_model
        self._optimizer_config = BUNNY_CONFIG.get("optimizer", {})
        self._optimizer_verified = None  # Cache verification result

    @property
    def optimizer_enabled(self) -> bool:
        """Check if Bunny Optimizer is enabled in config."""
        return self._optimizer_config.get("enabled", False)

    def _verify_optimizer(self) -> bool:
        """Verify optimizer is actually working (cached)."""
        if self._optimizer_verified is None:
            result = verify_optimizer_enabled()
            self._optimizer_verified = result.get("enabled", False)
        return self._optimizer_verified

    def upload_with_optimizer(
        self,
        source: str,
        file_name: str,
        alt_text: str,
        path_type: str = "articles",
        image_type: str = "hero"
    ) -> Dict[str, Any]:
        """
        Upload a single original image and generate optimizer URLs.

        This is the new optimized workflow:
        1. Upload only the original image
        2. Generate dynamic URLs with Bunny Optimizer params
        3. Return srcset/sizes for responsive images

        Args:
            source: Local file path or URL of the original image
            file_name: SEO-friendly filename for storage
            alt_text: Alt text for the image
            path_type: CDN path type (articles, newsletter, social)
            image_type: Type of image for sizes attribute (hero, section, thumbnail)

        Returns:
            Dict containing:
            - success: bool
            - cdn_url: str (base CDN URL of uploaded original)
            - optimizer_set: OptimizerImageSet with all URLs
            - srcset: str
            - sizes: str
            - primary_url: str
        """
        start_time = datetime.utcnow()

        try:
            # Upload original image
            logger.info(f"Uploading original image: {file_name}")
            upload_result = upload_to_bunny_storage(
                source=source,
                file_name=file_name,
                path_type=path_type
            )

            if not upload_result.get("success"):
                return {
                    "success": False,
                    "error": upload_result.get("error", "Upload failed")
                }

            cdn_url = upload_result["cdn_url"]
            logger.info(f"Original uploaded to: {cdn_url}")

            # Verify CDN propagation
            verification = verify_cdn_propagation(cdn_url)
            if not verification.get("propagated"):
                logger.warning(f"CDN propagation not verified: {verification.get('error')}")

            # Generate optimizer URLs
            responsive_widths = self._optimizer_config.get("responsive_widths", [480, 800, 1200, 2400])
            default_quality = self._optimizer_config.get("default_quality", 85)

            # Generate srcset using optimizer
            srcset_result = generate_responsive_srcset(
                base_url=cdn_url,
                widths=responsive_widths,
                quality=default_quality,
                format="auto" if self._optimizer_config.get("auto_format") else None,
                image_type=image_type
            )

            # Build OptimizerURL objects for each width
            optimizer_variants = []
            for width in responsive_widths:
                variant_url = srcset_result.get("urls", {}).get(width)
                if variant_url:
                    optimizer_variants.append(OptimizerURL(
                        base_url=cdn_url,
                        width=width,
                        quality=default_quality,
                        format="auto"
                    ))

            # Create OptimizerImageSet
            optimizer_set = OptimizerImageSet(
                original_url=cdn_url,
                variants=optimizer_variants,
                srcset=srcset_result.get("srcset", ""),
                sizes=srcset_result.get("sizes", ""),
                alt_text=alt_text,
                file_name=file_name,
                original_size_bytes=upload_result.get("file_size_bytes"),
                original_format=upload_result.get("content_type")
            )

            end_time = datetime.utcnow()
            total_time_ms = int((end_time - start_time).total_seconds() * 1000)

            return {
                "success": True,
                "cdn_url": cdn_url,
                "storage_path": upload_result["storage_path"],
                "optimizer_set": optimizer_set.dict(),
                "srcset": srcset_result.get("srcset", ""),
                "sizes": srcset_result.get("sizes", ""),
                "primary_url": srcset_result.get("primary_url", cdn_url),
                "responsive_urls": srcset_result.get("urls", {}),
                "file_size_bytes": upload_result.get("file_size_bytes", 0),
                "file_size_kb": upload_result.get("file_size_kb", 0),
                "upload_time_ms": total_time_ms,
                "propagation_verified": verification.get("propagated", False),
                "optimizer_enabled": True
            }

        except Exception as e:
            logger.error(f"Optimizer upload error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def upload_image_set(
        self,
        image_set: ResponsiveImageSet,
        path_type: str = "articles",
        use_optimizer: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Upload a complete image set to CDN.

        If Bunny Optimizer is enabled, uploads only the original and generates
        dynamic URLs. Otherwise, falls back to uploading all variants.

        Args:
            image_set: ResponsiveImageSet with optimized variants
            path_type: CDN path type (articles, newsletter, social)
            use_optimizer: Override optimizer setting (None = use config)

        Returns:
            Upload results with CDN URLs
        """
        # Determine whether to use optimizer
        should_use_optimizer = use_optimizer if use_optimizer is not None else self.optimizer_enabled

        if should_use_optimizer:
            # Use optimizer workflow - upload only original
            logger.info("Using Bunny Optimizer workflow")

            # Get image type from original
            img_type = image_set.original.image_type
            if isinstance(img_type, str):
                image_type = img_type.replace("_image", "")
            else:
                image_type = img_type.value.replace("_image", "") if hasattr(img_type, 'value') else "hero"

            return self.upload_with_optimizer(
                source=image_set.original.original_url,
                file_name=image_set.file_name,
                alt_text=image_set.alt_text,
                path_type=path_type,
                image_type=image_type
            )

        # Legacy workflow - upload all variants
        logger.info("Using legacy multi-variant upload workflow")
        start_time = datetime.utcnow()
        upload_results = []
        cdn_urls = {}

        try:
            for variant in image_set.variants:
                # Generate filename with suffix
                extension = f".{variant.format}" if isinstance(variant.format, str) else f".{variant.format.value}"
                filename = f"{image_set.file_name}{variant.suffix}{extension}"

                # Upload to CDN
                result = upload_to_bunny_storage(
                    source=variant.local_path,
                    file_name=filename,
                    path_type=path_type
                )

                if result.get("success"):
                    # Verify propagation
                    verification = verify_cdn_propagation(result["cdn_url"])

                    upload_result = CDNUploadResult(
                        success=True,
                        local_path=variant.local_path,
                        storage_path=result["storage_path"],
                        cdn_url=result["cdn_url"],
                        file_size_bytes=result["file_size_bytes"],
                        content_type=result["content_type"],
                        uploaded_at=datetime.utcnow(),
                        propagation_verified=verification.get("propagated", False)
                    )

                    cdn_urls[variant.suffix or "default"] = result["cdn_url"]
                else:
                    upload_result = CDNUploadResult(
                        success=False,
                        local_path=variant.local_path,
                        storage_path="",
                        cdn_url="",
                        file_size_bytes=0,
                        content_type="",
                        error_message=result.get("error")
                    )

                upload_results.append(upload_result.dict())

            end_time = datetime.utcnow()
            total_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # Determine primary URL (default/no suffix)
            primary_url = cdn_urls.get("default", cdn_urls.get("", list(cdn_urls.values())[0] if cdn_urls else ""))

            return {
                "success": all(r["success"] for r in upload_results),
                "upload_results": upload_results,
                "cdn_urls": cdn_urls,
                "primary_cdn_url": primary_url,
                "total_uploaded": len([r for r in upload_results if r["success"]]),
                "total_size_kb": sum(r["file_size_bytes"] for r in upload_results if r["success"]) / 1024,
                "upload_time_ms": total_time_ms
            }

        except Exception as e:
            logger.error(f"CDN upload error: {e}")
            return {
                "success": False,
                "error": str(e),
                "upload_results": upload_results
            }

    def upload_batch(
        self,
        image_sets: List[ResponsiveImageSet],
        path_type: str = "articles"
    ) -> Dict[str, Any]:
        """
        Upload multiple image sets to CDN.

        Args:
            image_sets: List of ResponsiveImageSet objects
            path_type: CDN path type

        Returns:
            Batch upload results
        """
        start_time = datetime.utcnow()
        results = []
        all_urls = []
        total_size_kb = 0

        for i, image_set in enumerate(image_sets):
            logger.info(f"Uploading image set {i + 1}/{len(image_sets)}: {image_set.file_name}")

            result = self.upload_image_set(
                image_set=image_set,
                path_type=path_type
            )

            results.append(result)

            if result.get("success"):
                # Handle both optimizer (responsive_urls dict) and legacy (cdn_urls dict) modes
                responsive_urls = result.get("responsive_urls", {})
                cdn_urls = result.get("cdn_urls", {})
                all_urls.extend(responsive_urls.values() if responsive_urls else cdn_urls.values())
                total_size_kb += result.get("total_size_kb", result.get("file_size_kb", 0))

        end_time = datetime.utcnow()
        total_time_ms = int((end_time - start_time).total_seconds() * 1000)

        return {
            "success": all(r.get("success") for r in results),
            "results": results,
            "total_sets": len(image_sets),
            "all_cdn_urls": all_urls,
            "total_size_kb": round(total_size_kb, 2),
            "total_time_ms": total_time_ms
        }

    def insert_images_in_markdown(
        self,
        markdown_content: str,
        image_results: List[ImageGenerationResult],
        article_title: str
    ) -> Dict[str, Any]:
        """
        Insert generated images into article markdown.

        Args:
            markdown_content: Original article markdown
            image_results: List of ImageGenerationResult with CDN URLs
            article_title: Article title for context

        Returns:
            Updated markdown content
        """
        try:
            lines = markdown_content.split('\n')
            insertions = []

            # Separate images by type
            hero_image = None
            section_images = []
            og_image = None

            for result in image_results:
                if not result.success or not result.primary_cdn_url:
                    continue

                img_type = result.image_type if isinstance(result.image_type, str) else result.image_type.value

                if img_type == "hero_image":
                    hero_image = result
                elif img_type == "section_image":
                    section_images.append(result)
                elif img_type == "og_card":
                    og_image = result

            # Find insertion points
            frontmatter_end = -1
            first_heading_line = -1

            in_frontmatter = False
            for i, line in enumerate(lines):
                if line.strip() == '---':
                    if not in_frontmatter:
                        in_frontmatter = True
                    else:
                        frontmatter_end = i
                        in_frontmatter = False
                elif line.strip().startswith('#') and first_heading_line == -1:
                    first_heading_line = i

            # Insert hero image after frontmatter or at top
            if hero_image:
                insert_line = frontmatter_end + 1 if frontmatter_end > -1 else 0

                hero_markdown = self._generate_image_markdown(
                    url=hero_image.primary_cdn_url,
                    alt=hero_image.alt_text or f"Featured image for {article_title}",
                    responsive_urls=hero_image.responsive_urls,
                    css_class="hero-image"
                )

                insertions.append((insert_line, hero_markdown))

            # Find H2 headings for section images
            h2_lines = []
            for i, line in enumerate(lines):
                if line.strip().startswith('## '):
                    h2_lines.append(i)

            # Insert section images after H2 headings
            if section_images and h2_lines:
                # Distribute evenly
                step = max(1, len(h2_lines) // len(section_images))
                selected_h2s = h2_lines[::step][:len(section_images)]

                for img, h2_line in zip(section_images, selected_h2s):
                    section_markdown = self._generate_image_markdown(
                        url=img.primary_cdn_url,
                        alt=img.alt_text or "Section illustration",
                        responsive_urls=img.responsive_urls,
                        css_class="section-image",
                        lazy=True
                    )

                    # Insert after the heading line
                    insertions.append((h2_line + 1, section_markdown))

            # Apply insertions (reverse order to maintain line numbers)
            insertions.sort(key=lambda x: x[0], reverse=True)

            for line_num, content in insertions:
                lines.insert(line_num, content)
                lines.insert(line_num, "")  # Add blank line before

            updated_markdown = '\n'.join(lines)

            # Get OG image URL for metadata
            og_url = og_image.primary_cdn_url if og_image else (hero_image.primary_cdn_url if hero_image else None)

            return {
                "success": True,
                "markdown": updated_markdown,
                "images_inserted": len(insertions),
                "og_image_url": og_url,
                "hero_image_url": hero_image.primary_cdn_url if hero_image else None
            }

        except Exception as e:
            logger.error(f"Markdown insertion error: {e}")
            return {
                "success": False,
                "error": str(e),
                "markdown": markdown_content
            }

    def _generate_image_markdown(
        self,
        url: str,
        alt: str,
        responsive_urls: Optional[Dict[str, str]] = None,
        srcset: Optional[str] = None,
        sizes: Optional[str] = None,
        css_class: Optional[str] = None,
        lazy: bool = False,
        optimizer_enabled: bool = False
    ) -> str:
        """
        Generate markdown/HTML for an image with optional responsive srcset.

        Args:
            url: Primary image URL
            alt: Alt text
            responsive_urls: Dict of size suffix/width -> URL for srcset (legacy)
            srcset: Pre-built srcset string (optimizer mode)
            sizes: Pre-built sizes string (optimizer mode)
            css_class: Optional CSS class
            lazy: Whether to add lazy loading
            optimizer_enabled: Whether using Bunny Optimizer URLs

        Returns:
            Image markdown/HTML string
        """
        class_attr = f' class="{css_class}"' if css_class else ''
        loading_attr = ' loading="lazy"' if lazy else ''

        # If we have pre-built srcset (optimizer mode), use it directly
        if srcset and sizes:
            return f'<img src="{url}" srcset="{srcset}" sizes="{sizes}" alt="{alt}"{class_attr}{loading_attr} />'

        # If we have responsive URLs (legacy mode), build srcset
        if responsive_urls and len(responsive_urls) > 1:
            srcset_parts = []
            for key, variant_url in responsive_urls.items():
                # Key can be suffix ("-md") or width (800)
                if isinstance(key, int):
                    width = f"{key}w"
                else:
                    # Extract width from suffix
                    width_map = {"": "1200w", "-md": "800w", "-sm": "480w", "-2x": "2400w", "default": "1200w"}
                    width = width_map.get(str(key), "1200w")
                srcset_parts.append(f"{variant_url} {width}")

            built_srcset = ", ".join(srcset_parts)
            built_sizes = "(max-width: 480px) 100vw, (max-width: 800px) 100vw, 1200px"

            return f'<img src="{url}" srcset="{built_srcset}" sizes="{built_sizes}" alt="{alt}"{class_attr}{loading_attr} />'

        # Simple markdown image
        return f'![{alt}]({url})'

    def purge_urls(self, urls: List[str]) -> Dict[str, Any]:
        """
        Purge CDN cache for multiple URLs.

        Args:
            urls: List of CDN URLs to purge

        Returns:
            Purge results
        """
        results = []
        for url in urls:
            result = purge_cdn_cache(url)
            results.append({
                "url": url,
                **result
            })

        return {
            "success": all(r.get("success") for r in results),
            "results": results,
            "purged_count": sum(1 for r in results if r.get("success"))
        }
