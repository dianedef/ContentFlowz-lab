"""
Image Pipeline - Deterministic image generation and CDN management system.
Coordinates 4 specialized components for automated image generation, optimization,
and CDN deployment for blog articles.

Components:
1. Image Strategist - Analyzes content and defines visual strategy
2. Image Generator - Generates images via Robolly API
3. Image Optimizer - Compresses and creates responsive variants
4. CDN Manager - Uploads to Bunny.net and manages CDN delivery
"""

from agents.images.image_crew import ImagePipeline, create_image_pipeline

__all__ = [
    "ImagePipeline",
    "create_image_pipeline"
]
