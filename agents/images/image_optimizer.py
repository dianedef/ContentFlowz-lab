"""
Image Optimizer Agent
Compresses and creates responsive variants of generated images
"""
from typing import Dict, Any, List, Optional, Union
import os
import logging
from pathlib import Path
from datetime import datetime
import tempfile

from agents.images.tools.optimization_tools import (
    compress_image,
    convert_to_webp,
    generate_responsive_variants,
    calculate_image_hash,
    get_image_info,
    resize_image
)
from agents.images.tools.strategy_tools import generate_seo_filename
from agents.images.schemas.image_schemas import (
    GeneratedImage,
    OptimizedImage,
    ResponsiveImageSet,
    ImageFormat
)
from agents.images.config.image_config import IMAGE_PROCESSING_CONFIG, BUNNY_CONFIG

logger = logging.getLogger(__name__)


class ImageOptimizer:
    """
    High-level interface for the Image Optimizer agent.
    Provides methods for optimizing images.

    When Bunny Optimizer is enabled, this class performs minimal processing
    (quality checks only) since transformations happen on-the-fly via CDN.
    """

    def __init__(
        self,
        llm_model: str = "gpt-4o-mini",
        temp_dir: Optional[str] = None
    ):
        self.llm_model = llm_model
        self.temp_dir = temp_dir or tempfile.mkdtemp(prefix="image-robot-")
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
        self._optimizer_config = BUNNY_CONFIG.get("optimizer", {})

    @property
    def optimizer_enabled(self) -> bool:
        """Check if Bunny Optimizer is enabled."""
        return self._optimizer_config.get("enabled", False)

    @property
    def fallback_to_local(self) -> bool:
        """Check if should fall back to local processing when optimizer disabled."""
        return self._optimizer_config.get("fallback_to_local", True)

    def prepare_for_optimizer(
        self,
        generated: GeneratedImage,
        article_title: str
    ) -> Dict[str, Any]:
        """
        Prepare an image for Bunny Optimizer workflow.

        When using CDN-based optimization, we only need to:
        1. Download the original image
        2. Perform quality checks
        3. Generate SEO filename and alt text
        4. Return the local path for upload

        No resizing or format conversion is needed - the CDN handles that.

        Args:
            generated: GeneratedImage from Robolly
            article_title: Article title for filename/alt generation

        Returns:
            Dict with local_path, file_name, alt_text, and quality info
        """
        start_time = datetime.utcnow()

        try:
            import requests

            # Download image to temp location
            image_type = generated.image_type if isinstance(generated.image_type, str) else generated.image_type.value
            temp_filename = f"original_{image_type}_{datetime.now().timestamp()}.jpg"
            temp_path = os.path.join(self.temp_dir, temp_filename)

            response = requests.get(generated.original_url, timeout=30)
            response.raise_for_status()

            with open(temp_path, 'wb') as f:
                f.write(response.content)

            file_size = os.path.getsize(temp_path)

            # Get image info for quality check
            info = get_image_info(temp_path)

            # Calculate hash for SEO filename
            file_hash = calculate_image_hash(temp_path)

            # Generate SEO filename
            from agents.images.tools.strategy_tools import generate_seo_filename, generate_alt_text

            seo_filename = generate_seo_filename(
                title=article_title,
                image_type=image_type,
                file_hash=file_hash.get("short_hash")
            )

            alt_text = generate_alt_text(
                title=article_title,
                image_type=image_type
            )

            end_time = datetime.utcnow()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

            return {
                "success": True,
                "local_path": temp_path,
                "file_name": seo_filename,
                "alt_text": alt_text,
                "file_size_bytes": file_size,
                "file_size_kb": round(file_size / 1024, 2),
                "width": info.get("width"),
                "height": info.get("height"),
                "format": info.get("format"),
                "file_hash": file_hash.get("hash"),
                "processing_time_ms": processing_time_ms,
                "optimizer_ready": True
            }

        except Exception as e:
            logger.error(f"Prepare for optimizer error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def optimize_image(
        self,
        generated: GeneratedImage,
        article_title: str,
        generate_responsive: bool = True,
        output_format: str = "webp",
        use_optimizer: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Fully optimize a generated image.

        If Bunny Optimizer is enabled, performs minimal processing and prepares
        the image for CDN upload. Otherwise, generates local variants.

        Args:
            generated: GeneratedImage object
            article_title: Article title for filename generation
            generate_responsive: Whether to create responsive variants (ignored if optimizer enabled)
            output_format: Output format (webp, jpg) (ignored if optimizer enabled)
            use_optimizer: Override optimizer setting (None = use config)

        Returns:
            Optimization results with ResponsiveImageSet
        """
        # Determine whether to use optimizer
        should_use_optimizer = use_optimizer if use_optimizer is not None else self.optimizer_enabled

        if should_use_optimizer:
            # Use simplified optimizer workflow
            logger.info("Using Bunny Optimizer workflow - minimal local processing")
            prep_result = self.prepare_for_optimizer(generated, article_title)

            if not prep_result.get("success"):
                return prep_result

            # Build a minimal ResponsiveImageSet for the optimizer workflow
            # The actual responsive URLs will be generated by CDNManager
            image_set = ResponsiveImageSet(
                original=generated,
                variants=[],  # No local variants needed
                srcset="",  # Will be generated by CDN manager with optimizer URLs
                sizes="",
                alt_text=prep_result["alt_text"],
                file_name=prep_result["file_name"],
                optimizer_enabled=True
            )

            return {
                "success": True,
                "image_set": image_set.dict(),
                "local_path": prep_result["local_path"],
                "file_name": prep_result["file_name"],
                "alt_text": prep_result["alt_text"],
                "variants_count": 0,  # No local variants
                "original_size_kb": prep_result["file_size_kb"],
                "total_size_kb": prep_result["file_size_kb"],
                "total_savings_percent": 0,  # Savings happen at CDN level
                "processing_time_ms": prep_result["processing_time_ms"],
                "optimizer_enabled": True
            }

        # Legacy workflow - full local processing
        logger.info("Using legacy local optimization workflow")
        start_time = datetime.utcnow()

        try:
            import requests

            # Download image to temp location
            image_type = generated.image_type if isinstance(generated.image_type, str) else generated.image_type.value
            temp_filename = f"temp_{image_type}_{datetime.now().timestamp()}.jpg"
            temp_path = os.path.join(self.temp_dir, temp_filename)

            response = requests.get(generated.original_url, timeout=30)
            response.raise_for_status()

            with open(temp_path, 'wb') as f:
                f.write(response.content)

            original_size = os.path.getsize(temp_path)

            # Get size target for image type
            max_size_kb = IMAGE_PROCESSING_CONFIG["max_file_sizes_kb"].get(
                image_type.replace("_image", ""),
                150
            )

            # Generate SEO filename
            file_hash = calculate_image_hash(temp_path)
            seo_filename = generate_seo_filename(
                title=article_title,
                image_type=image_type,
                file_hash=file_hash.get("short_hash")
            )

            optimized_variants = []

            if generate_responsive:
                # Generate responsive variants
                responsive_type = image_type.replace("_image", "")
                if responsive_type == "og_card":
                    responsive_type = "hero"  # OG cards use hero sizes

                variants_result = generate_responsive_variants(
                    input_path=temp_path,
                    output_dir=self.temp_dir,
                    image_type=responsive_type,
                    output_format=output_format
                )

                if variants_result.get("success"):
                    for variant in variants_result.get("variants", []):
                        variant_hash = calculate_image_hash(variant["path"])

                        optimized = OptimizedImage(
                            source_image_id=generated.robolly_render_id,
                            format=ImageFormat(output_format),
                            width=variant["width"],
                            height=variant["height"],
                            quality=IMAGE_PROCESSING_CONFIG["compression"].get(f"{output_format}_quality", 82),
                            file_size_bytes=int(variant["size_kb"] * 1024),
                            compression_ratio=round(variant["size_kb"] * 1024 / original_size, 3),
                            local_path=variant["path"],
                            file_hash=variant_hash.get("hash", ""),
                            suffix=variant["suffix"]
                        )
                        optimized_variants.append(optimized)

                    srcset = variants_result.get("srcset", "")
                    sizes = variants_result.get("sizes", "")
                else:
                    logger.warning(f"Responsive variants failed: {variants_result.get('error')}")
                    srcset = ""
                    sizes = ""
            else:
                # Just convert to WebP
                webp_path = os.path.join(self.temp_dir, f"{seo_filename}.webp")
                webp_result = convert_to_webp(
                    input_path=temp_path,
                    output_path=webp_path
                )

                if webp_result.get("success"):
                    webp_hash = calculate_image_hash(webp_path)
                    info = get_image_info(webp_path)

                    optimized = OptimizedImage(
                        source_image_id=generated.robolly_render_id,
                        format=ImageFormat.WEBP,
                        width=info.get("width", generated.dimensions.get("width", 1200)),
                        height=info.get("height", generated.dimensions.get("height", 630)),
                        quality=IMAGE_PROCESSING_CONFIG["compression"]["webp_quality"],
                        file_size_bytes=int(webp_result["webp_size_kb"] * 1024),
                        compression_ratio=round(webp_result["webp_size_kb"] / (original_size / 1024), 3),
                        local_path=webp_path,
                        file_hash=webp_hash.get("hash", ""),
                        suffix=""
                    )
                    optimized_variants.append(optimized)

                srcset = ""
                sizes = ""

            # Build responsive image set
            from agents.images.tools.strategy_tools import generate_alt_text

            alt_text = generate_alt_text(
                title=article_title,
                image_type=image_type
            )

            image_set = ResponsiveImageSet(
                original=generated,
                variants=optimized_variants,
                srcset=srcset,
                sizes=sizes,
                alt_text=alt_text,
                file_name=seo_filename,
                placement_markdown=None  # Will be set by CDN Manager
            )

            end_time = datetime.utcnow()
            total_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # Calculate total size
            total_size_kb = sum(v.file_size_bytes for v in optimized_variants) / 1024

            return {
                "success": True,
                "image_set": image_set.dict(),
                "variants_count": len(optimized_variants),
                "total_size_kb": round(total_size_kb, 2),
                "original_size_kb": round(original_size / 1024, 2),
                "total_savings_percent": round((1 - total_size_kb / (original_size / 1024)) * 100, 1),
                "processing_time_ms": total_time_ms
            }

        except Exception as e:
            logger.error(f"Optimization error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def optimize_batch(
        self,
        generated_images: List[GeneratedImage],
        article_title: str,
        generate_responsive: bool = True
    ) -> Dict[str, Any]:
        """
        Optimize multiple generated images.

        Args:
            generated_images: List of GeneratedImage objects
            article_title: Article title for filenames
            generate_responsive: Whether to create responsive variants

        Returns:
            Batch optimization results
        """
        start_time = datetime.utcnow()
        results = []
        successful = 0
        failed = 0
        total_size_kb = 0

        for i, generated in enumerate(generated_images):
            logger.info(f"Optimizing image {i + 1}/{len(generated_images)}")

            result = self.optimize_image(
                generated=generated,
                article_title=article_title,
                generate_responsive=generate_responsive
            )

            results.append(result)

            if result.get("success"):
                successful += 1
                total_size_kb += result.get("total_size_kb", 0)
            else:
                failed += 1

        end_time = datetime.utcnow()
        total_time_ms = int((end_time - start_time).total_seconds() * 1000)

        return {
            "success": failed == 0,
            "results": results,
            "total": len(generated_images),
            "successful": successful,
            "failed": failed,
            "total_size_kb": round(total_size_kb, 2),
            "total_time_ms": total_time_ms
        }

    def cleanup_temp_files(self):
        """Clean up temporary files"""
        import shutil
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp files: {e}")
