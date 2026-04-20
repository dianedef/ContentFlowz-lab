"""Pydantic models for Project management and onboarding"""

from pydantic import BaseModel, HttpUrl, Field, model_validator
from typing import Optional, Literal, List
from enum import Enum
from datetime import datetime


# ─────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────

class Framework(str, Enum):
    """Detected web framework types"""
    ASTRO = "astro"
    NEXTJS = "nextjs"
    GATSBY = "gatsby"
    NUXT = "nuxt"
    HUGO = "hugo"
    JEKYLL = "jekyll"
    UNKNOWN = "unknown"


class PackageManager(str, Enum):
    """Package manager types"""
    NPM = "npm"
    YARN = "yarn"
    PNPM = "pnpm"
    PIP = "pip"
    UNKNOWN = "unknown"


class OnboardingStatus(str, Enum):
    """Project onboarding workflow status"""
    PENDING = "pending"
    CLONING = "cloning"
    ANALYZING = "analyzing"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"


# ─────────────────────────────────────────────────
# Detection Models
# ─────────────────────────────────────────────────

class TechStackDetection(BaseModel):
    """Detected technology stack from repository analysis"""
    framework: Framework = Field(
        default=Framework.UNKNOWN,
        description="Detected web framework"
    )
    framework_version: Optional[str] = Field(
        default=None,
        description="Framework version from package.json"
    )
    package_manager: PackageManager = Field(
        default=PackageManager.UNKNOWN,
        description="Detected package manager"
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Detection confidence (0-1)"
    )


class ContentDirectoryConfig(BaseModel):
    """Content directory configuration"""
    path: str = Field(
        ...,
        description="Path to content directory (e.g., 'src/content')"
    )
    auto_detected: bool = Field(
        default=True,
        description="Whether this was auto-detected or user-specified"
    )
    file_extensions: list[str] = Field(
        default=[".md", ".mdx"],
        description="Content file extensions to process"
    )


class ProjectConfigOverrides(BaseModel):
    """SEO and content configuration overrides"""
    seo_config: Optional[dict] = Field(
        default=None,
        description="SEO-specific configuration overrides"
    )
    linking_config: Optional[dict] = Field(
        default=None,
        description="Internal linking configuration overrides"
    )
    content_config: Optional[dict] = Field(
        default=None,
        description="Content processing configuration overrides"
    )


# ─────────────────────────────────────────────────
# Project Models
# ─────────────────────────────────────────────────

class ProjectSettings(BaseModel):
    """Project settings stored in database JSON field"""
    tech_stack: Optional[TechStackDetection] = None
    content_directories: List[ContentDirectoryConfig] = Field(
        default_factory=list,
        description="Content directories configured by the user (ordered by priority)"
    )
    config_overrides: Optional[ProjectConfigOverrides] = None
    onboarding_status: OnboardingStatus = OnboardingStatus.PENDING
    local_repo_path: Optional[str] = Field(
        default=None,
        description="Local path to cloned repository"
    )
    analytics_enabled: bool = Field(
        default=False,
        description="Whether cookie-free analytics tracking is enabled for this project. "
                    "When enabled, a lightweight script (<1KB) is injected into the site layout "
                    "to collect anonymous pageview data (no cookies, no IP storage, EU-hosted)."
    )

    @model_validator(mode='before')
    @classmethod
    def migrate_single_content_directory(cls, data: dict) -> dict:
        """Backward compat: migrate old single content_directory to content_directories list."""
        if isinstance(data, dict) and 'content_directory' in data and 'content_directories' not in data:
            old = data.pop('content_directory')
            if old is not None:
                data['content_directories'] = [old]
        return data


class Project(BaseModel):
    """Complete project model matching database schema"""
    id: str = Field(..., description="Unique project identifier")
    user_id: str = Field(..., description="Owner user ID")
    name: str = Field(..., description="Project display name")
    url: str = Field(..., description="GitHub repository URL")
    type: str = Field(default="github", description="Repository type")
    description: Optional[str] = Field(default=None, description="Project description")
    is_default: bool = Field(default=False, description="Whether this is the default project")
    settings: Optional[ProjectSettings] = Field(default=None, description="Project settings JSON")
    last_analyzed_at: Optional[datetime] = Field(default=None, description="Last analysis timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")


# ─────────────────────────────────────────────────
# Request Models
# ─────────────────────────────────────────────────

class OnboardProjectRequest(BaseModel):
    """Request to start project onboarding"""
    github_url: HttpUrl = Field(
        ...,
        description="GitHub repository URL",
        examples=["https://github.com/user/my-site"]
    )
    name: Optional[str] = Field(
        default=None,
        description="Optional project name (defaults to repo name)"
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional project description"
    )


class AnalyzeProjectRequest(BaseModel):
    """Request to analyze a project"""
    force_reclone: bool = Field(
        default=False,
        description="Force re-clone even if repo exists locally"
    )


class ConfirmProjectRequest(BaseModel):
    """Request to confirm or override project settings"""
    project_id: str = Field(..., description="Project ID to confirm")
    confirmed: bool = Field(
        default=True,
        description="Accept auto-detected settings"
    )
    content_directories_override: Optional[List[ContentDirectoryConfig]] = Field(
        default=None,
        description="Override content directories if not confirmed"
    )
    config_overrides: Optional[ProjectConfigOverrides] = Field(
        default=None,
        description="Additional configuration overrides"
    )
    analytics_enabled: bool = Field(
        default=False,
        description="Enable cookie-free analytics. Injects a lightweight tracking script (<1KB) "
                    "into your site layout. No cookies, no IP storage, EU-hosted. "
                    "Required for pageview analytics, SEO performance tracking, and content insights "
                    "in the dashboard."
    )


class UpdateProjectRequest(BaseModel):
    """Request to update project details"""
    name: Optional[str] = Field(default=None, description="New project name")
    github_url: Optional[HttpUrl] = Field(
        default=None,
        description="Updated GitHub repository URL"
    )
    description: Optional[str] = Field(default=None, description="New description")
    content_directories: Optional[List[ContentDirectoryConfig]] = Field(
        default=None,
        description="Update content directories"
    )
    config_overrides: Optional[ProjectConfigOverrides] = Field(
        default=None,
        description="Update configuration overrides"
    )
    analytics_enabled: Optional[bool] = Field(
        default=None,
        description="Enable or disable cookie-free analytics for this project"
    )


# ─────────────────────────────────────────────────
# Response Models
# ─────────────────────────────────────────────────

class OnboardProjectResponse(BaseModel):
    """Response from starting project onboarding"""
    project_id: str = Field(..., description="Created project ID")
    status: OnboardingStatus = Field(..., description="Current onboarding status")
    message: str = Field(..., description="Status message")


class ProjectDetectionResult(BaseModel):
    """Result from project analysis/detection"""
    project_id: str = Field(..., description="Project ID")
    tech_stack: TechStackDetection = Field(..., description="Detected technology stack")
    content_directories: list[str] = Field(
        ...,
        description="All detected content directories"
    )
    suggested_content_dir: Optional[str] = Field(
        default=None,
        description="Suggested primary content directory"
    )
    total_content_files: int = Field(
        default=0,
        description="Number of content files found"
    )
    framework_config_found: bool = Field(
        default=False,
        description="Whether framework config file was found"
    )


class ProjectResponse(BaseModel):
    """Full project response"""
    id: str
    user_id: str
    name: str
    url: str
    type: str
    description: Optional[str]
    is_default: bool
    settings: Optional[ProjectSettings]
    last_analyzed_at: Optional[datetime]
    created_at: datetime


class ProjectListResponse(BaseModel):
    """List of projects response"""
    projects: list[ProjectResponse]
    total: int
    default_project_id: Optional[str] = None
