"""Agent dependencies for FastAPI dependency injection

IMPORTANT: Uses lazy imports to avoid loading heavy ML dependencies
(torch, spacy) at startup. This allows FastAPI to bind to port quickly
and pass Render's health check.
"""

from functools import lru_cache
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Type hints only (not loaded at runtime)
if TYPE_CHECKING:
    from agents.seo.topical_mesh_architect import TopicalMeshArchitect
    from agents.seo.research_analyst import ResearchAnalystAgent
    from agents.seo.content_strategist import ContentStrategistAgent
    from agents.images.image_crew import ImagePipeline


@lru_cache()
def get_mesh_architect() -> "TopicalMeshArchitect":
    """
    Get or create TopicalMeshArchitect singleton

    Uses LRU cache to reuse the same instance across requests
    (agents are stateless, safe to reuse)

    LAZY IMPORT: Heavy dependencies only loaded on first request
    """
    from agents.seo.topical_mesh_architect import TopicalMeshArchitect
    return TopicalMeshArchitect()


@lru_cache()
def get_research_analyst() -> "ResearchAnalystAgent":
    """Get or create ResearchAnalystAgent singleton (lazy import)"""
    from agents.seo.research_analyst import ResearchAnalystAgent
    return ResearchAnalystAgent()


@lru_cache()
def get_content_strategist() -> "ContentStrategistAgent":
    """Get or create ContentStrategistAgent singleton (lazy import)"""
    from agents.seo.content_strategist import ContentStrategistAgent
    return ContentStrategistAgent()


@lru_cache()
def get_image_pipeline() -> "ImagePipeline":
    """
    Get or create ImagePipeline singleton (lazy import).

    Coordinates 4 specialized components:
    - Image Strategist: Analyzes content and plans visual strategy
    - Image Generator: Creates images via Robolly API
    - Image Optimizer: Compresses and creates responsive variants
    - CDN Manager: Uploads to Bunny.net and integrates with content
    """
    from agents.images.image_crew import ImagePipeline
    return ImagePipeline()
