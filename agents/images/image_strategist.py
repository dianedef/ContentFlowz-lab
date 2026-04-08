"""
Image Strategist Agent
Analyzes article content and defines optimal visual strategy
"""
from typing import Dict, Any, Optional
import logging

from agents.images.tools.strategy_tools import (
    analyze_article_for_images,
    extract_key_topics,
    determine_image_count,
    select_templates_for_article
)
from agents.images.schemas.image_schemas import ImageStrategy, ImageBrief, ImageType

logger = logging.getLogger(__name__)


class ImageStrategist:
    """
    High-level interface for the Image Strategist agent.
    Provides methods for analyzing articles and creating image strategies.
    """

    def __init__(self, llm_model: str = "gpt-4o-mini"):
        self.llm_model = llm_model

    def analyze_article(
        self,
        content: str,
        title: str,
        slug: str,
        strategy_type: Optional[str] = None,
        style_guide: str = "brand_primary"
    ) -> Dict[str, Any]:
        """
        Analyze an article and create image strategy.

        Args:
            content: Article markdown content
            title: Article title
            slug: Article URL slug
            strategy_type: Optional strategy override
            style_guide: Style guide to use

        Returns:
            ImageStrategy as dict
        """
        try:
            # Use tools directly for faster processing
            analysis = analyze_article_for_images(
                content=content,
                title=title,
                strategy_type=strategy_type
            )

            if not analysis.get("success"):
                return {
                    "success": False,
                    "error": analysis.get("error", "Analysis failed")
                }

            topics = extract_key_topics(
                content=content,
                title=title,
                max_topics=5
            )

            # Get template selections
            image_types = [img["image_type"] for img in analysis["recommended_images"]]
            templates = select_templates_for_article(
                image_types=image_types,
                style_guide=style_guide
            )

            # Build image briefs
            image_briefs = []
            for img in analysis["recommended_images"]:
                img_type = img["image_type"]
                template_config = templates["templates"].get(img_type, {})

                brief = ImageBrief(
                    image_type=ImageType(img_type),
                    title_text=img["title_text"],
                    subtitle_text=img.get("subtitle_text"),
                    template_id=template_config.get("template_id"),
                    placement_hint=img.get("placement_hint"),
                    context_keywords=topics.get("keywords", [])[:3]
                )
                image_briefs.append(brief)

            # Build strategy
            strategy = ImageStrategy(
                article_title=title,
                article_slug=slug,
                article_topics=topics.get("topics", []),
                article_word_count=analysis["word_count"],
                strategy_type=analysis["recommended_strategy"],
                style_guide=style_guide,
                num_images=len(image_briefs),
                image_briefs=image_briefs,
                generate_og_card=any(b.image_type == ImageType.OG_CARD for b in image_briefs),
                generate_responsive=True
            )

            return {
                "success": True,
                "strategy": strategy.dict(),
                "analysis": analysis,
                "templates": templates
            }

        except Exception as e:
            logger.error(f"Error analyzing article: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def quick_strategy(
        self,
        title: str,
        word_count: int,
        heading_count: int = 0,
        strategy_type: str = "standard"
    ) -> Dict[str, Any]:
        """
        Quick strategy determination without full article analysis.

        Args:
            title: Article title
            word_count: Approximate word count
            heading_count: Number of H2 headings
            strategy_type: Strategy to use

        Returns:
            Quick strategy recommendation
        """
        counts = determine_image_count(
            word_count=word_count,
            heading_count=heading_count,
            strategy_type=strategy_type
        )

        return {
            "title": title,
            "recommended_images": counts.get("total_images", 2),
            "breakdown": counts.get("breakdown", {}),
            "strategy": strategy_type
        }
