"""
Image Robot Crew - Multi-Agent Image Generation and CDN Management System
Orchestrates 4 specialized agents for automated image generation, optimization,
and CDN deployment for blog articles.

Workflow:
1. Image Strategist - Analyzes article and creates visual strategy
2. Image Generator - Generates images via Robolly API
3. Image Optimizer - Compresses and creates responsive variants
4. CDN Manager - Uploads to Bunny.net and inserts into markdown
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import logging
from pathlib import Path

from agents.shared.run_history import RunHistory
from agents.images.image_strategist import ImageStrategist
from agents.images.image_generator import ImageGenerator
from agents.images.image_optimizer import ImageOptimizer
from agents.images.cdn_manager import CDNManager
from agents.images.schemas.image_schemas import (
    ImageStrategy,
    ImageBrief,
    GeneratedImage,
    ResponsiveImageSet,
    ArticleWithImages,
    ImageGenerationResult,
    ImageType,
    OptimizerImageSet
)
from agents.images.config.image_config import ImageConfig, BUNNY_CONFIG

logger = logging.getLogger(__name__)

# Conditional status tracking (graceful degradation)
try:
    from status import get_status_service
    STATUS_AVAILABLE = True
except ImportError:
    STATUS_AVAILABLE = False


class ImageRobotCrew:
    """
    Image Robot Crew orchestrating image generation and CDN workflows.

    This crew coordinates 4 specialized agents:
    - Image Strategist: Analyzes content and plans visual strategy
    - Image Generator: Creates images via Robolly API
    - Image Optimizer: Compresses and creates responsive variants
    - CDN Manager: Uploads to Bunny.net and integrates with content
    """

    def __init__(
        self,
        llm_model: str = "gpt-4o-mini",
        project_path: str = "/root/contentflowz-lab"
    ):
        """
        Initialize Image Robot Crew with all agents.

        Args:
            llm_model: LLM model to use for all agents
            project_path: Path to project directory
        """
        self.llm_model = llm_model
        self.project_path = project_path

        # Initialize agents
        self.strategist = ImageStrategist(llm_model)
        self.generator = ImageGenerator(llm_model)
        self.optimizer = ImageOptimizer(llm_model)
        self.cdn_manager = CDNManager(llm_model)

        # Data directory
        self.data_dir = Path(project_path) / "data" / "images"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Optimizer configuration
        self._optimizer_config = BUNNY_CONFIG.get("optimizer", {})

        optimizer_status = "enabled" if self._optimizer_config.get("enabled") else "disabled"
        logger.info(f"Image Robot Crew initialized (Bunny Optimizer: {optimizer_status})")

    @property
    def optimizer_enabled(self) -> bool:
        """Check if Bunny Optimizer is enabled."""
        return self._optimizer_config.get("enabled", False)

    def process(
        self,
        article_content: str,
        article_title: str,
        article_slug: str,
        article_topics: Optional[List[str]] = None,
        strategy_type: Optional[str] = None,
        style_guide: str = "brand_primary",
        generate_responsive: bool = True,
        path_type: str = "articles"
    ) -> ArticleWithImages:
        """
        Complete pipeline: Strategize → Generate → Optimize → Deploy → Integrate

        Args:
            article_content: Markdown content of the article
            article_title: Title of the article
            article_slug: URL slug for the article
            article_topics: Optional list of topics (will be extracted if not provided)
            strategy_type: Optional strategy override (minimal, standard, hero+sections, rich)
            style_guide: Style guide to use for branding
            generate_responsive: Whether to generate responsive variants
            path_type: CDN path type (articles, newsletter, social)

        Returns:
            ArticleWithImages with enriched markdown and all image metadata
        """
        start_time = datetime.utcnow()
        workflow_id = f"img_{int(start_time.timestamp())}"

        logger.info(f"Starting Image Robot workflow {workflow_id} for '{article_title}'")

        # Status tracking: create content record
        status_record_id = None
        if STATUS_AVAILABLE:
            try:
                status_svc = get_status_service()
                record = status_svc.create_content(
                    title=f"Images: {article_title}",
                    content_type="image",
                    source_robot="images",
                    status="in_progress",
                    tags=article_topics or [],
                    metadata={
                        "article_slug": article_slug,
                        "strategy_type": strategy_type,
                        "style_guide": style_guide,
                        "path_type": path_type,
                    },
                )
                status_record_id = record.id
                logger.info(f"Status tracking: record {record.id} created (in_progress)")
            except Exception as e:
                logger.warning(f"Status tracking init failed (non-critical): {e}")

        with RunHistory().start("image_robot", "generate_images", inputs={
            "article_title": article_title,
            "article_slug": article_slug,
            "strategy_type": strategy_type,
        }) as run:
            try:
                # Step 1: Strategy Analysis
                logger.info("Step 1: Analyzing article and creating strategy")
                strategy_result = self.strategist.analyze_article(
                    content=article_content,
                    title=article_title,
                    slug=article_slug,
                    strategy_type=strategy_type,
                    style_guide=style_guide
                )

                if not strategy_result.get("success"):
                    run.mark_failed(f"Strategy failed: {strategy_result.get('error')}")
                    return self._create_error_result(
                        article_title, article_slug, article_content,
                        f"Strategy failed: {strategy_result.get('error')}"
                    )

                strategy = ImageStrategy(**strategy_result["strategy"])
                logger.info(f"Strategy: {strategy.strategy_type}, {strategy.num_images} images")

                # Step 2: Image Generation
                logger.info("Step 2: Generating images via Robolly")
                generation_result = self.generator.generate_batch(
                    briefs=strategy.image_briefs,
                    style_guide=style_guide
                )

                if generation_result.get("failed", 0) == len(strategy.image_briefs):
                    run.mark_failed("All image generations failed")
                    return self._create_error_result(
                        article_title, article_slug, article_content,
                        f"All image generations failed"
                    )

                # Extract successful generations
                generated_images = []
                for result in generation_result.get("results", []):
                    if result.get("result", {}).get("success"):
                        generated = GeneratedImage(**result["result"]["generated"])
                        generated_images.append(generated)

                logger.info(f"Generated {len(generated_images)}/{len(strategy.image_briefs)} images")

                # Step 3: Optimization
                logger.info("Step 3: Optimizing images")
                optimization_result = self.optimizer.optimize_batch(
                    generated_images=generated_images,
                    article_title=article_title,
                    generate_responsive=generate_responsive
                )

                # Extract successful optimizations
                image_sets = []
                for result in optimization_result.get("results", []):
                    if result.get("success"):
                        image_set = ResponsiveImageSet(**result["image_set"])
                        image_sets.append(image_set)

                logger.info(f"Optimized {len(image_sets)} image sets")

                # Step 4: CDN Upload
                logger.info("Step 4: Uploading to CDN")
                upload_result = self.cdn_manager.upload_batch(
                    image_sets=image_sets,
                    path_type=path_type
                )

                # Build image results with CDN URLs
                image_results = []
                for i, (image_set, upload_res) in enumerate(zip(image_sets, upload_result.get("results", []))):
                    if upload_res.get("success"):
                        # Handle both optimizer (responsive_urls with int keys) and legacy (cdn_urls with str keys)
                        responsive_urls = upload_res.get("responsive_urls", {})
                        cdn_urls = upload_res.get("cdn_urls", {})

                        # Convert integer width keys to string for consistent handling
                        if responsive_urls:
                            normalized_urls = {str(k): v for k, v in responsive_urls.items()}
                        else:
                            normalized_urls = cdn_urls

                        # Get primary URL - optimizer uses 'primary_url', legacy uses 'primary_cdn_url'
                        primary_url = upload_res.get("primary_url") or upload_res.get("primary_cdn_url")

                        img_result = ImageGenerationResult(
                            success=True,
                            image_type=image_set.original.image_type,
                            generated=image_set.original,
                            optimized=image_set.variants,
                            cdn_uploads=upload_res.get("upload_results", []),
                            primary_cdn_url=primary_url,
                            responsive_urls=normalized_urls,
                            alt_text=image_set.alt_text,
                            file_name=image_set.file_name
                        )
                    else:
                        img_result = ImageGenerationResult(
                            success=False,
                            image_type=image_set.original.image_type,
                            errors=[upload_res.get("error", "Upload failed")]
                        )

                    image_results.append(img_result)

                logger.info(f"Uploaded {sum(1 for r in image_results if r.success)} images to CDN")

                # Step 5: Insert Images into Markdown
                logger.info("Step 5: Inserting images into markdown")
                insertion_result = self.cdn_manager.insert_images_in_markdown(
                    markdown_content=article_content,
                    image_results=image_results,
                    article_title=article_title
                )

                # Build final result
                end_time = datetime.utcnow()
                total_time_ms = int((end_time - start_time).total_seconds() * 1000)

                # Collect all CDN URLs
                all_cdn_urls = []
                for result in image_results:
                    if result.success and result.primary_cdn_url:
                        all_cdn_urls.append(result.primary_cdn_url)
                        all_cdn_urls.extend(result.responsive_urls.values())

                # Calculate total CDN size (handle both optimizer and legacy modes)
                total_cdn_size_kb = sum(
                    upload_res.get("total_size_kb", upload_res.get("file_size_kb", 0))
                    for upload_res in upload_result.get("results", [])
                    if upload_res.get("success")
                )

                # Generate schema.org metadata
                image_metadata = self._generate_image_schema(
                    image_results=image_results,
                    article_title=article_title
                )

                article_with_images = ArticleWithImages(
                    article_title=article_title,
                    article_slug=article_slug,
                    original_content=article_content,
                    markdown_with_images=insertion_result.get("markdown", article_content),
                    strategy=strategy,
                    images=image_results,
                    total_images=len(image_results),
                    successful_images=sum(1 for r in image_results if r.success),
                    failed_images=sum(1 for r in image_results if not r.success),
                    image_metadata=image_metadata,
                    og_image_url=insertion_result.get("og_image_url"),
                    total_cdn_size_kb=total_cdn_size_kb,
                    cdn_urls=list(set(all_cdn_urls)),
                    processing_time_ms=total_time_ms,
                    processed_at=end_time
                )

                run.set_outputs({
                    "workflow_id": workflow_id,
                    "total_images": article_with_images.total_images,
                    "successful_images": article_with_images.successful_images,
                    "failed_images": article_with_images.failed_images,
                    "processing_time_ms": article_with_images.processing_time_ms,
                })

                # Status tracking: mark as generated → pending_review
                if STATUS_AVAILABLE and status_record_id:
                    try:
                        status_svc = get_status_service()
                        status_svc.update_content(
                            status_record_id,
                            metadata={
                                "total_images": article_with_images.total_images,
                                "successful_images": article_with_images.successful_images,
                                "failed_images": article_with_images.failed_images,
                                "total_cdn_size_kb": article_with_images.total_cdn_size_kb,
                                "processing_time_ms": total_time_ms,
                            },
                        )
                        status_svc.transition(status_record_id, "generated", "images_robot")
                        status_svc.transition(status_record_id, "pending_review", "images_robot")
                        logger.info(f"Status tracking: marked as pending_review")
                    except Exception as se:
                        logger.warning(f"Status tracking completion failed (non-critical): {se}")

                logger.info(f"Workflow {workflow_id} completed in {total_time_ms}ms")

                return article_with_images

            except Exception as e:
                logger.error(f"Workflow error: {e}")
                run.mark_failed(str(e))
                # Status tracking: mark as failed
                if STATUS_AVAILABLE and status_record_id:
                    try:
                        status_svc = get_status_service()
                        status_svc.transition(status_record_id, "failed", "images_robot", reason=str(e))
                    except Exception as se:
                        logger.warning(f"Status tracking failed transition error: {se}")
                return self._create_error_result(
                    article_title, article_slug, article_content,
                    str(e)
                )

            finally:
                # Cleanup temp files
                self.optimizer.cleanup_temp_files()

    def quick_process(
        self,
        article_content: str,
        article_title: str,
        article_slug: str,
        hero_only: bool = True
    ) -> ArticleWithImages:
        """
        Quick processing with minimal images (hero + OG only).

        Args:
            article_content: Article markdown
            article_title: Article title
            article_slug: Article slug
            hero_only: If True, only generate hero image

        Returns:
            ArticleWithImages
        """
        return self.process(
            article_content=article_content,
            article_title=article_title,
            article_slug=article_slug,
            strategy_type="minimal" if hero_only else "standard",
            generate_responsive=False
        )

    def regenerate_images(
        self,
        article_with_images: ArticleWithImages,
        failed_only: bool = True
    ) -> ArticleWithImages:
        """
        Regenerate images for an article (retry failed ones).

        Args:
            article_with_images: Previous result
            failed_only: If True, only regenerate failed images

        Returns:
            Updated ArticleWithImages
        """
        briefs_to_regenerate = []

        for result, brief in zip(article_with_images.images, article_with_images.strategy.image_briefs):
            if failed_only and result.success:
                continue
            briefs_to_regenerate.append(brief)

        if not briefs_to_regenerate:
            logger.info("No images to regenerate")
            return article_with_images

        # Regenerate
        return self.process(
            article_content=article_with_images.original_content,
            article_title=article_with_images.article_title,
            article_slug=article_with_images.article_slug,
            strategy_type=article_with_images.strategy.strategy_type,
            style_guide=article_with_images.strategy.style_guide
        )

    def _create_error_result(
        self,
        title: str,
        slug: str,
        content: str,
        error: str
    ) -> ArticleWithImages:
        """Create an error result when workflow fails"""
        return ArticleWithImages(
            article_title=title,
            article_slug=slug,
            original_content=content,
            markdown_with_images=content,  # Return original content
            strategy=ImageStrategy(
                article_title=title,
                article_slug=slug,
                num_images=0,
                image_briefs=[]
            ),
            images=[],
            total_images=0,
            successful_images=0,
            failed_images=0,
            image_metadata={"error": error}
        )

    def _generate_image_schema(
        self,
        image_results: List[ImageGenerationResult],
        article_title: str
    ) -> Dict[str, Any]:
        """Generate schema.org ImageObject metadata"""
        images_schema = []

        for result in image_results:
            if not result.success or not result.primary_cdn_url:
                continue

            image_schema = {
                "@type": "ImageObject",
                "url": result.primary_cdn_url,
                "name": result.file_name,
                "description": result.alt_text or f"Image for {article_title}",
                "contentUrl": result.primary_cdn_url
            }

            if result.generated:
                image_schema["width"] = result.generated.dimensions.get("width", 1200)
                image_schema["height"] = result.generated.dimensions.get("height", 630)

            images_schema.append(image_schema)

        return {
            "@context": "https://schema.org",
            "image": images_schema
        }


def create_image_robot_crew(
    llm_model: str = "gpt-4o-mini",
    project_path: str = "/root/contentflowz-lab"
) -> ImageRobotCrew:
    """
    Factory function to create Image Robot Crew.

    Args:
        llm_model: LLM model for all agents
        project_path: Project directory path

    Returns:
        Initialized ImageRobotCrew instance
    """
    return ImageRobotCrew(
        llm_model=llm_model,
        project_path=project_path
    )


# Example usage
if __name__ == "__main__":
    import sys

    # Validate configuration
    config_status = ImageConfig.validate()
    print("Configuration Status:")
    print(json.dumps(config_status, indent=2))

    if not config_status["valid"]:
        print("\nConfiguration issues found:")
        for issue in config_status["issues"]:
            print(f"  - {issue}")
        sys.exit(1)

    # Example article
    example_article = """---
title: "Getting Started with AI Agents in 2026"
slug: ai-agents-getting-started
---

# Getting Started with AI Agents in 2026

Artificial intelligence agents are transforming how we build software.
In this comprehensive guide, we'll explore everything you need to know.

## What are AI Agents?

AI agents are autonomous systems that can perceive their environment,
make decisions, and take actions to achieve specific goals.

## Building Your First Agent

Let's walk through the process of building a simple AI agent
using modern frameworks like CrewAI and LangChain.

## Best Practices

Here are the key best practices for building effective AI agents
that are reliable, efficient, and maintainable.

## Conclusion

AI agents represent a paradigm shift in software development.
Start building today and join the future of automation.
"""

    # Create crew and process
    crew = create_image_robot_crew()

    print("\nProcessing article...")
    result = crew.process(
        article_content=example_article,
        article_title="Getting Started with AI Agents in 2026",
        article_slug="ai-agents-getting-started",
        strategy_type="standard"
    )

    print(f"\nResults:")
    print(f"  Total images: {result.total_images}")
    print(f"  Successful: {result.successful_images}")
    print(f"  Failed: {result.failed_images}")
    print(f"  Processing time: {result.processing_time_ms}ms")
    print(f"  CDN URLs: {len(result.cdn_urls)}")

    if result.og_image_url:
        print(f"  OG Image: {result.og_image_url}")
