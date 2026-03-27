"""
Scheduler Robot Configuration
Central configuration for all scheduler agents and workflows
"""
import os
from pathlib import Path
from typing import Dict, Any
import yaml


class SchedulerConfig:
    """Configuration management for Scheduler Robot"""

    def __init__(self, config_dir: str = None):
        if config_dir is None:
            config_dir = Path(__file__).parent

        self.config_dir = Path(config_dir)
        self.calendar_rules = self._load_calendar_rules()

    def _load_calendar_rules(self) -> Dict[str, Any]:
        """Load calendar rules from YAML"""
        rules_file = self.config_dir / "calendar_rules.yaml"

        if rules_file.exists():
            with open(rules_file, 'r') as f:
                return yaml.safe_load(f)
        else:
            return self._get_default_calendar_rules()

    def _get_default_calendar_rules(self) -> Dict[str, Any]:
        """Default calendar rules if file doesn't exist"""
        return {
            "publishing_rules": [
                {
                    "name": "Peak Weekday Hours",
                    "days": ["Monday", "Tuesday", "Wednesday", "Thursday"],
                    "times": ["09:00", "14:00", "18:00"],
                    "timezone": "America/New_York"
                }
            ],
            "blackout_dates": [],
            "content_rules": [],
            "scheduling_settings": {
                "global_minimum_spacing_hours": 4,
                "queue_warning_threshold": 20,
                "max_queue_days": 14,
                "auto_schedule_enabled": True,
                "default_timezone": "America/New_York"
            }
        }

    # LLM Configuration
    LLM_MODEL = os.getenv("SCHEDULER_LLM_MODEL", "mixtral-8x7b-32768")
    LLM_TEMPERATURE = float(os.getenv("SCHEDULER_LLM_TEMPERATURE", "0.3"))

    # Google API Configuration
    GOOGLE_SEARCH_CONSOLE_CREDENTIALS = os.getenv("GOOGLE_SEARCH_CONSOLE_CREDENTIALS")
    GOOGLE_INDEXING_API_KEY = os.getenv("GOOGLE_INDEXING_API_KEY")

    # GitHub Configuration (for deployment)
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    GITHUB_REPO = os.getenv("GITHUB_REPO", "username/repo")

    # Project Paths
    PROJECT_PATH = os.getenv("SCHEDULER_PROJECT_PATH", "/root/contentflowz-lab")
    DATA_DIR = os.getenv("SCHEDULER_DATA_DIR", "/root/contentflowz-lab/data/scheduler")

    # Site Configuration
    BASE_URL = os.getenv("SCHEDULER_BASE_URL", "http://localhost:3000")
    PRODUCTION_URL = os.getenv("SCHEDULER_PRODUCTION_URL", "https://yoursite.com")

    # Audit Frequency
    AUDIT_FREQUENCY = os.getenv("SCHEDULER_AUDIT_FREQUENCY", "weekly")  # daily, weekly, monthly
    AUTO_FIX_ENABLED = os.getenv("SCHEDULER_AUTO_FIX", "false").lower() == "true"

    # Publishing Settings
    PUBLISH_AUTO_DEPLOY = os.getenv("PUBLISH_AUTO_DEPLOY", "true").lower() == "true"
    PUBLISH_REQUIRE_APPROVAL = os.getenv("PUBLISH_REQUIRE_APPROVAL", "false").lower() == "true"
    PUBLISH_TIMEZONE = os.getenv("PUBLISH_TIMEZONE", "America/New_York")

    # Monitoring and Notifications
    NOTIFY_EMAIL = os.getenv("SCHEDULER_NOTIFY_EMAIL")
    NOTIFY_SLACK_WEBHOOK = os.getenv("SCHEDULER_NOTIFY_SLACK_WEBHOOK")
    NOTIFY_ON_CRITICAL = os.getenv("SCHEDULER_NOTIFY_ON_CRITICAL", "true").lower() == "true"

    # Performance Thresholds
    PERF_THRESHOLD_PAGE_SPEED = int(os.getenv("SCHEDULER_PERF_PAGE_SPEED", "90"))
    PERF_THRESHOLD_SEO_SCORE = int(os.getenv("SCHEDULER_PERF_SEO_SCORE", "85"))
    PERF_THRESHOLD_BUILD_TIME = int(os.getenv("SCHEDULER_PERF_BUILD_TIME", "120"))  # seconds

    # Cost Tracking
    COST_WARNING_THRESHOLD = float(os.getenv("SCHEDULER_COST_WARNING", "100.0"))  # USD/month
    COST_CRITICAL_THRESHOLD = float(os.getenv("SCHEDULER_COST_CRITICAL", "500.0"))  # USD/month

    @classmethod
    def get_calendar_rules(cls) -> Dict[str, Any]:
        """Get calendar rules"""
        config = cls()
        return config.calendar_rules

    @classmethod
    def get_scheduling_settings(cls) -> Dict[str, Any]:
        """Get scheduling settings"""
        config = cls()
        return config.calendar_rules.get('scheduling_settings', {})

    @classmethod
    def validate_config(cls) -> Dict[str, Any]:
        """Validate configuration and return status"""
        issues = []
        warnings = []

        # Check required API keys
        if not cls.GOOGLE_SEARCH_CONSOLE_CREDENTIALS:
            warnings.append("Google Search Console credentials not configured")

        if not cls.GOOGLE_INDEXING_API_KEY:
            warnings.append("Google Indexing API key not configured")

        if not cls.GITHUB_TOKEN:
            warnings.append("GitHub token not configured - deployment will fail")

        # Check paths
        if not Path(cls.PROJECT_PATH).exists():
            issues.append(f"Project path does not exist: {cls.PROJECT_PATH}")

        # Check LLM
        if not os.getenv("GROQ_API_KEY"):
            issues.append("GROQ_API_KEY not set - agents will fail")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }


# Create singleton instance
config = SchedulerConfig()
