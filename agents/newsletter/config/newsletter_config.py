"""
Newsletter Configuration - Default settings and environment loading.
"""

import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# Email backend selection: "imap" (free, direct) or "composio" (paid, managed)
EMAIL_BACKEND = os.getenv("NEWSLETTER_EMAIL_BACKEND", "imap")

# IMAP configuration (for EMAIL_BACKEND="imap")
IMAP_DEFAULTS: Dict[str, Any] = {
    "host": os.getenv("NEWSLETTER_IMAP_HOST", "imap.gmail.com"),
    "email": os.getenv("NEWSLETTER_IMAP_EMAIL"),
    "app_password": os.getenv("NEWSLETTER_IMAP_PASSWORD"),
    "newsletter_folder": os.getenv("NEWSLETTER_IMAP_FOLDER", "Newsletters"),
    "archive_folder": os.getenv("NEWSLETTER_IMAP_ARCHIVE", "CONTENTFLOW_DONE"),
    "days_to_scan": int(os.getenv("NEWSLETTER_IMAP_DAYS", "7")),
    "max_emails": int(os.getenv("NEWSLETTER_IMAP_MAX_EMAILS", "20")),
}

# Default newsletter settings
NEWSLETTER_DEFAULTS: Dict[str, Any] = {
    # LLM settings
    "llm_model": os.getenv("NEWSLETTER_LLM_MODEL", "openrouter/anthropic/claude-3.5-sonnet"),

    # Content settings
    "max_sections": 5,
    "max_words_per_section": 300,
    "include_intro": True,
    "include_outro": True,
    "include_cta": True,

    # Email settings
    "days_to_scan": 7,  # How many days of emails to analyze
    "max_emails_to_read": 20,

    # SendGrid settings
    "sendgrid_api_key": os.getenv("SENDGRID_API_KEY"),
    "from_email": os.getenv("NEWSLETTER_FROM_EMAIL", "newsletter@example.com"),
    "from_name": os.getenv("NEWSLETTER_FROM_NAME", "Newsletter"),

    # Templates
    "template_dir": os.getenv(
        "NEWSLETTER_TEMPLATE_DIR",
        os.path.join(os.path.dirname(__file__), "..", "templates")
    ),
}


def get_newsletter_config(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Get newsletter configuration with optional overrides.

    Args:
        overrides: Dictionary of settings to override defaults

    Returns:
        Complete configuration dictionary
    """
    config = NEWSLETTER_DEFAULTS.copy()

    if overrides:
        config.update(overrides)

    return config


def validate_config() -> Dict[str, bool]:
    """
    Validate that required configuration is present.

    Returns:
        Dictionary of config keys and their validity
    """
    checks = {
        "sendgrid_configured": bool(os.getenv("SENDGRID_API_KEY")),
        "composio_configured": bool(os.getenv("COMPOSIO_API_KEY")),
        "exa_configured": bool(os.getenv("EXA_API_KEY")),
        "openrouter_configured": bool(os.getenv("OPENROUTER_API_KEY")),
        "imap_configured": bool(
            IMAP_DEFAULTS["email"] and IMAP_DEFAULTS["app_password"]
        ),
    }

    return checks


def get_email_backend() -> str:
    """
    Get the configured email backend.

    Returns:
        "imap" or "composio"
    """
    return EMAIL_BACKEND


def is_imap_backend() -> bool:
    """Check if IMAP backend is configured."""
    return EMAIL_BACKEND == "imap"


def get_imap_config() -> Dict[str, Any]:
    """
    Get IMAP configuration.

    Returns:
        IMAP configuration dictionary
    """
    return IMAP_DEFAULTS.copy()
