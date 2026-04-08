"""
Image Generator Agent
Generates images using Robolly API based on strategy briefs
"""
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from agents.images.tools.robolly_tools import (
    generate_robolly_image,
    validate_robolly_image,
    get_robolly_templates,
    generate_image_for_type,
    download_image
)
from agents.images.schemas.image_schemas import (
    GeneratedImage,
    ImageBrief,
    ImageType,
    ImageFormat
)
from agents.images.config.image_config import ROBOLLY_CONFIG

logger = logging.getLogger(__name__)


class ImageGenerator:
    """
    High-level interface for the Image Generator agent.
    Provides methods for generating images from briefs.
    """

    def __init__(self, llm_model: str = "gpt-4o-mini"):
        self.llm_model = llm_model

    def generate_from_brief(
        self,
        brief: ImageBrief,
        style_guide: str = "brand_primary",
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Generate a single image from a brief.

        Args:
            brief: ImageBrief with generation parameters
            style_guide: Style guide to apply
            max_retries: Maximum retry attempts

        Returns:
            Generation result with GeneratedImage if successful
        """
        start_time = datetime.utcnow()
        last_error = None

        for attempt in range(max_retries):
            try:
                # Get template ID
                template_id = brief.template_id
                if not template_id:
                    # Get default template for type
                    template_config = ROBOLLY_CONFIG["templates"].get(brief.image_type.value, {})
                    template_id = template_config.get("template_id")

                if not template_id:
                    return {
                        "success": False,
                        "error": f"No template configured for {brief.image_type.value}"
                    }

                # Generate image
                result = generate_robolly_image(
                    template_id=template_id,
                    title=brief.title_text,
                    subtitle=brief.subtitle_text,
                    style_guide=style_guide
                )

                if not result.get("success"):
                    last_error = result.get("error", "Generation failed")
                    logger.warning(f"Generation attempt {attempt + 1} failed: {last_error}")
                    continue

                # Validate image
                validation = validate_robolly_image(result["image_url"])
                if not validation.get("valid"):
                    last_error = f"Validation failed: {validation.get('error')}"
                    logger.warning(f"Validation attempt {attempt + 1} failed: {last_error}")
                    continue

                # Success - build GeneratedImage
                end_time = datetime.utcnow()
                total_time_ms = int((end_time - start_time).total_seconds() * 1000)

                generated = GeneratedImage(
                    image_type=brief.image_type,
                    robolly_render_id=result["render_id"],
                    original_url=result["image_url"],
                    title_text=brief.title_text,
                    template_id=template_id,
                    style_guide=style_guide,
                    dimensions=result.get("dimensions", {"width": 1200, "height": 630}),
                    format=ImageFormat(result.get("format", "jpg")),
                    file_size_bytes=validation.get("size_bytes"),
                    generated_at=datetime.utcnow(),
                    generation_time_ms=result.get("generation_time_ms", total_time_ms)
                )

                return {
                    "success": True,
                    "generated": generated.dict(),
                    "attempts": attempt + 1,
                    "total_time_ms": total_time_ms
                }

            except Exception as e:
                last_error = str(e)
                logger.error(f"Generation attempt {attempt + 1} error: {e}")

        return {
            "success": False,
            "error": last_error or "Max retries exceeded",
            "attempts": max_retries
        }

    def generate_batch(
        self,
        briefs: List[ImageBrief],
        style_guide: str = "brand_primary"
    ) -> Dict[str, Any]:
        """
        Generate multiple images from a list of briefs.

        Args:
            briefs: List of ImageBrief objects
            style_guide: Style guide to apply

        Returns:
            Batch generation results
        """
        start_time = datetime.utcnow()
        results = []
        successful = 0
        failed = 0

        for i, brief in enumerate(briefs):
            logger.info(f"Generating image {i + 1}/{len(briefs)}: {brief.image_type.value}")

            result = self.generate_from_brief(
                brief=brief,
                style_guide=style_guide
            )

            results.append({
                "brief_index": i,
                "image_type": brief.image_type.value,
                "result": result
            })

            if result.get("success"):
                successful += 1
            else:
                failed += 1

        end_time = datetime.utcnow()
        total_time_ms = int((end_time - start_time).total_seconds() * 1000)

        return {
            "success": failed == 0,
            "results": results,
            "total": len(briefs),
            "successful": successful,
            "failed": failed,
            "total_time_ms": total_time_ms
        }

    def download_generated_image(
        self,
        image_url: str,
        local_path: str
    ) -> Dict[str, Any]:
        """
        Download a generated image to local storage.

        Args:
            image_url: URL of generated image
            local_path: Local path to save to

        Returns:
            Download result
        """
        return download_image(image_url, local_path)

    def get_available_templates(self) -> Dict[str, Any]:
        """
        Get list of configured templates.

        Returns:
            Template configuration
        """
        return get_robolly_templates()
