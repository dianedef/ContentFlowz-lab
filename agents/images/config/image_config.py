"""
Image Robot Configuration
Central configuration for Robolly API, Bunny.net CDN, and image processing settings
"""
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


# Robolly API Configuration
ROBOLLY_CONFIG = {
    "api_key": os.getenv("ROBOLLY_API_KEY"),
    "base_url": "https://api.robolly.com",

    # Rate limiting
    "max_requests_per_minute": 60,
    "retry_attempts": 3,
    "retry_delay_seconds": 2,

    # Polling settings
    "poll_interval_seconds": 1,
    "poll_max_attempts": 30,

    # Templates configuration
    "templates": {
        "hero_image": {
            "template_id": os.getenv("ROBOLLY_TEMPLATE_HERO", ""),
            "dimensions": {"width": 1200, "height": 630},
            "format": "jpg",
            "quality": 90,
            "description": "Main hero image for blog posts"
        },
        "section_image": {
            "template_id": os.getenv("ROBOLLY_TEMPLATE_SECTION", ""),
            "dimensions": {"width": 800, "height": 450},
            "format": "jpg",
            "quality": 85,
            "description": "Section break images within articles"
        },
        "og_card": {
            "template_id": os.getenv("ROBOLLY_TEMPLATE_OG", ""),
            "dimensions": {"width": 1200, "height": 630},
            "format": "jpg",
            "quality": 90,
            "description": "Open Graph social sharing cards"
        },
        "thumbnail": {
            "template_id": os.getenv("ROBOLLY_TEMPLATE_THUMBNAIL", ""),
            "dimensions": {"width": 400, "height": 300},
            "format": "jpg",
            "quality": 80,
            "description": "Thumbnail images for listings"
        }
    },

    # Style guides (branding)
    "style_guides": {
        "brand_primary": {
            "colors": {
                "primary": os.getenv("BRAND_COLOR_PRIMARY", "#2563eb"),
                "secondary": os.getenv("BRAND_COLOR_SECONDARY", "#64748b"),
                "accent": os.getenv("BRAND_COLOR_ACCENT", "#f59e0b"),
                "text": os.getenv("BRAND_COLOR_TEXT", "#1f2937"),
                "background": os.getenv("BRAND_COLOR_BG", "#ffffff")
            },
            "logo_url": os.getenv("BRAND_LOGO_URL", ""),
            "font_family": os.getenv("BRAND_FONT", "Inter"),
            "overlay_opacity": 0.7
        },
        "brand_dark": {
            "colors": {
                "primary": "#3b82f6",
                "secondary": "#94a3b8",
                "accent": "#fbbf24",
                "text": "#f9fafb",
                "background": "#111827"
            },
            "logo_url": os.getenv("BRAND_LOGO_DARK_URL", ""),
            "font_family": "Inter",
            "overlay_opacity": 0.8
        },
        "minimal": {
            "colors": {
                "primary": "#000000",
                "secondary": "#6b7280",
                "accent": "#000000",
                "text": "#111827",
                "background": "#ffffff"
            },
            "logo_url": "",
            "font_family": "Georgia",
            "overlay_opacity": 0.5
        }
    }
}


# Bunny.net CDN Configuration
BUNNY_CONFIG = {
    "storage": {
        "api_key": os.getenv("BUNNY_STORAGE_API_KEY"),
        "storage_zone": os.getenv("BUNNY_STORAGE_ZONE", "contentflow-images"),
        "base_url": "https://storage.bunnycdn.com",
        "region": os.getenv("BUNNY_STORAGE_REGION", "de"),  # de, ny, la, sg, syd
        "hostname": os.getenv("BUNNY_CDN_HOSTNAME", ""),
    },
    "cdn": {
        "api_key": os.getenv("BUNNY_CDN_API_KEY"),
        "pull_zone_id": os.getenv("BUNNY_PULL_ZONE_ID"),
        "base_url": "https://api.bunny.net",
    },
    "optimizer": {
        # Core settings
        "enabled": True,
        "default_quality": 85,

        # Format auto-detection
        "auto_webp": True,
        "auto_avif": True,
        "auto_format": True,  # Let Bunny pick best format based on browser

        # Responsive image widths for srcset generation
        "responsive_widths": [480, 800, 1200, 2400],

        # JPEG settings
        "progressive_jpeg": True,

        # Cache settings for optimized images
        "cache_enabled": True,

        # Fallback to local PIL processing if optimizer unavailable
        "fallback_to_local": True,
    },
    "cache": {
        "max_age_seconds": 31536000,  # 1 year
        "stale_while_revalidate": 86400,  # 1 day
    },
    "paths": {
        "articles": "/articles/images/",
        "newsletter": "/newsletter/images/",
        "social": "/social/images/",
        "thumbnails": "/thumbnails/"
    }
}


# Image Processing Configuration
IMAGE_PROCESSING_CONFIG = {
    "compression": {
        "jpeg_quality": 85,
        "webp_quality": 82,
        "avif_quality": 80,
        "png_compression": 9,
    },
    "responsive_sizes": {
        "hero": [
            {"width": 1200, "suffix": ""},
            {"width": 800, "suffix": "-md"},
            {"width": 480, "suffix": "-sm"},
            {"width": 2400, "suffix": "-2x"}
        ],
        "section": [
            {"width": 800, "suffix": ""},
            {"width": 600, "suffix": "-md"},
            {"width": 400, "suffix": "-sm"}
        ],
        "thumbnail": [
            {"width": 400, "suffix": ""},
            {"width": 200, "suffix": "-sm"}
        ]
    },
    "max_file_sizes_kb": {
        "hero": 150,
        "section": 80,
        "thumbnail": 30,
        "og_card": 100
    },
    "supported_formats": ["jpg", "jpeg", "png", "webp", "avif"],
    "default_output_format": "webp"
}


# Image Strategy Configuration
IMAGE_STRATEGY_CONFIG = {
    "strategies": {
        "minimal": {
            "description": "Only hero image",
            "image_types": ["hero_image"],
            "max_images": 1
        },
        "standard": {
            "description": "Hero + OG card",
            "image_types": ["hero_image", "og_card"],
            "max_images": 2
        },
        "hero+sections": {
            "description": "Hero + 2-3 section images + OG card",
            "image_types": ["hero_image", "section_image", "og_card"],
            "max_images": 5,
            "sections_per_1000_words": 1
        },
        "rich": {
            "description": "Hero + many sections + OG + thumbnails",
            "image_types": ["hero_image", "section_image", "og_card", "thumbnail"],
            "max_images": 10,
            "sections_per_1000_words": 2
        }
    },
    "auto_detect_threshold": {
        "short_article_words": 500,
        "medium_article_words": 1500,
        "long_article_words": 3000
    }
}


@dataclass
class ImageConfig:
    """Centralized Image Robot configuration"""

    # LLM Configuration
    llm_model: str = os.getenv("IMAGE_ROBOT_LLM_MODEL", "gpt-4o-mini")
    llm_temperature: float = float(os.getenv("IMAGE_ROBOT_LLM_TEMPERATURE", "0.3"))

    # Project Paths
    project_path: str = os.getenv("PROJECT_PATH", "/root/contentflow_lab")
    data_dir: str = os.getenv("IMAGE_ROBOT_DATA_DIR", "/root/contentflow_lab/data/images")
    temp_dir: str = os.getenv("IMAGE_ROBOT_TEMP_DIR", "/tmp/image-robot")

    # Feature Flags
    enable_webp_conversion: bool = True
    enable_avif_conversion: bool = False  # AVIF support is newer
    enable_responsive_images: bool = True
    enable_lazy_loading: bool = True

    # Quality Settings
    target_hero_size_kb: int = 150
    target_section_size_kb: int = 80
    min_image_quality: int = 70
    max_image_quality: int = 95

    # Retry and Timeout
    api_timeout_seconds: int = 30
    max_retry_attempts: int = 3
    retry_backoff_factor: float = 2.0

    # Monitoring
    notify_on_failure: bool = True
    log_level: str = os.getenv("IMAGE_ROBOT_LOG_LEVEL", "INFO")

    def __post_init__(self):
        """Create necessary directories"""
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate(cls) -> Dict[str, Any]:
        """Validate configuration and return status"""
        issues = []
        warnings = []

        # Check Robolly API key
        if not ROBOLLY_CONFIG["api_key"]:
            issues.append("ROBOLLY_API_KEY not set - image generation will fail")

        # Check Robolly templates
        templates_configured = sum(
            1 for t in ROBOLLY_CONFIG["templates"].values()
            if t["template_id"]
        )
        if templates_configured == 0:
            warnings.append("No Robolly templates configured - using default templates")

        # Check Bunny.net API keys
        if not BUNNY_CONFIG["storage"]["api_key"]:
            issues.append("BUNNY_STORAGE_API_KEY not set - CDN upload will fail")

        if not BUNNY_CONFIG["storage"]["hostname"]:
            issues.append("BUNNY_CDN_HOSTNAME not set - CDN URLs cannot be generated")

        # Check brand configuration
        if not ROBOLLY_CONFIG["style_guides"]["brand_primary"]["logo_url"]:
            warnings.append("Brand logo URL not configured - images won't include logo")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "templates_configured": templates_configured,
            "robolly_configured": bool(ROBOLLY_CONFIG["api_key"]),
            "bunny_configured": bool(BUNNY_CONFIG["storage"]["api_key"])
        }

    @staticmethod
    def get_template_config(template_type: str) -> Dict[str, Any]:
        """Get configuration for a specific template type"""
        return ROBOLLY_CONFIG["templates"].get(template_type, {})

    @staticmethod
    def get_style_guide(style_name: str) -> Dict[str, Any]:
        """Get a specific style guide configuration"""
        return ROBOLLY_CONFIG["style_guides"].get(style_name,
            ROBOLLY_CONFIG["style_guides"]["brand_primary"])

    @staticmethod
    def get_cdn_path(path_type: str) -> str:
        """Get CDN path for a specific content type"""
        return BUNNY_CONFIG["paths"].get(path_type, "/images/")

    @staticmethod
    def get_strategy_config(strategy_name: str) -> Dict[str, Any]:
        """Get configuration for a specific image strategy"""
        return IMAGE_STRATEGY_CONFIG["strategies"].get(strategy_name,
            IMAGE_STRATEGY_CONFIG["strategies"]["standard"])


# Create singleton instance
config = ImageConfig()
