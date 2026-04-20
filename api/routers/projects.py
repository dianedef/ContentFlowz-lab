"""Projects API endpoints.

Handles project onboarding workflow and CRUD operations.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Any, List, Optional

from api.models.project import (
    OnboardProjectRequest,
    OnboardProjectResponse,
    AnalyzeProjectRequest,
    ProjectDetectionResult,
    ConfirmProjectRequest,
    UpdateProjectRequest,
    ProjectResponse,
    ProjectListResponse,
    Project,
    OnboardingStatus,
)
from agents.seo.services.project_onboarding import project_onboarding_service
from agents.seo.config.project_store import project_store
from agents.scheduler.tools.content_scanner import get_content_scanner
from agents.scheduler.tools.cluster_scheduler import get_cluster_scheduler
from api.dependencies.auth import CurrentUser, require_current_user
from api.services.user_data_store import user_data_store


router = APIRouter(
    prefix="/api/projects",
    tags=["Projects"],
    responses={404: {"description": "Project not found"}},
)


def project_to_response(project: Project, *, default_project_id: str | None = None) -> ProjectResponse:
    """Convert Project model to response format."""
    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        url=project.url,
        type=project.type,
        description=project.description,
        is_default=project.id == default_project_id,
        settings=project.settings,
        last_analyzed_at=project.last_analyzed_at,
        created_at=project.created_at
    )


async def get_user_default_project_id(user_id: str) -> str | None:
    """Return the last-opened project id stored in user settings."""
    settings = await user_data_store.get_user_settings(user_id)
    default_project_id = settings.get("defaultProjectId")
    return default_project_id if isinstance(default_project_id, str) else None


async def require_owned_project(
    project_id: str,
    current_user: CurrentUser,
) -> Project:
    """Load a project and ensure the current user owns it."""
    project = await project_store.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return project


# ─────────────────────────────────────────────────
# Onboarding Endpoints
# ─────────────────────────────────────────────────

@router.post(
    "/onboard",
    response_model=OnboardProjectResponse,
    summary="Start project onboarding",
    description="""
    Start the onboarding process for a new project.

    **What it does:**
    - Creates a new project record
    - Prepares for repository analysis
    - Returns project_id for subsequent steps

    **Next step:** Call `/api/projects/{id}/analyze` to analyze the repository.

    **Example:**
    ```json
    {
      "github_url": "https://github.com/user/my-site"
    }
    ```
    """
)
async def onboard_project(
    request: OnboardProjectRequest,
    current_user: CurrentUser = Depends(require_current_user),
) -> OnboardProjectResponse:
    """Start onboarding a new project."""
    return await project_onboarding_service.initiate_onboarding(
        user_id=current_user.user_id,
        github_url=str(request.github_url),
        name=request.name,
        description=request.description
    )


@router.post(
    "",
    response_model=ProjectResponse,
    summary="Create project",
    description="Create a project record directly from a GitHub repository URL."
)
async def create_project(
    request: OnboardProjectRequest,
    current_user: CurrentUser = Depends(require_current_user),
) -> Any:
    """Create a project without running the full onboarding wizard."""
    project = await project_store.create(
        user_id=current_user.user_id,
        name=request.name or str(request.github_url).rstrip("/").split("/")[-1],
        url=str(request.github_url),
        description=request.description,
    )
    default_project_id = await get_user_default_project_id(current_user.user_id)
    return project_to_response(project, default_project_id=default_project_id)


@router.post(
    "/{project_id}/analyze",
    response_model=ProjectDetectionResult,
    summary="Analyze project repository",
    description="""
    Clone and analyze the project repository.

    **What it does:**
    - Clones the GitHub repository
    - Detects framework (Astro, Next.js, etc.)
    - Detects package manager (npm, yarn, pnpm)
    - Finds content directories
    - Counts content files

    **Next step:** Call `/api/projects/{id}/confirm` to confirm or override settings.

    **Returns:**
    - Detected tech stack with confidence score
    - List of content directories
    - Suggested primary content directory
    """
)
async def analyze_project(
    project_id: str,
    request: AnalyzeProjectRequest = AnalyzeProjectRequest(),
    current_user: CurrentUser = Depends(require_current_user),
) -> ProjectDetectionResult:
    """Analyze project repository and detect settings."""
    await require_owned_project(project_id, current_user)
    try:
        return await project_onboarding_service.analyze_project(
            project_id=project_id,
            force_reclone=request.force_reclone
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{project_id}/confirm",
    response_model=ProjectResponse,
    summary="Confirm project settings",
    description="""
    Confirm or override the detected project settings.

    **What it does:**
    - Accepts auto-detected settings OR
    - Applies user overrides for content directory
    - Applies configuration overrides
    - Marks onboarding as complete

    **Example - Accept detected settings:**
    ```json
    {
      "project_id": "uuid-here",
      "confirmed": true
    }
    ```

    **Example - Override content directories:**
    ```json
    {
      "project_id": "uuid-here",
      "confirmed": false,
      "content_directories_override": [
        {"path": "src/content/blog", "auto_detected": false, "file_extensions": [".md", ".mdx"]},
        {"path": "src/content/docs", "auto_detected": false, "file_extensions": [".md", ".mdx"]}
      ]
    }
    ```
    """
)
async def confirm_project(
    project_id: str,
    request: ConfirmProjectRequest,
    current_user: CurrentUser = Depends(require_current_user),
) -> Any:
    """Confirm or override project settings."""
    # Ensure project_id in path matches request
    if request.project_id != project_id:
        request.project_id = project_id
    await require_owned_project(project_id, current_user)

    try:
        project = await project_onboarding_service.confirm_project(request)
        default_project_id = await get_user_default_project_id(current_user.user_id)
        return project_to_response(project, default_project_id=default_project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─────────────────────────────────────────────────
# CRUD Endpoints
# ─────────────────────────────────────────────────

@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List all projects",
    description="Get all projects for the current user."
)
async def list_projects(
    current_user: CurrentUser = Depends(require_current_user),
) -> ProjectListResponse:
    """Get all projects for current user."""
    projects = await project_store.get_by_user(current_user.user_id)
    default_project_id = await get_user_default_project_id(current_user.user_id)

    return ProjectListResponse(
        projects=[
            project_to_response(p, default_project_id=default_project_id)
            for p in projects
        ],
        total=len(projects),
        default_project_id=default_project_id
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project details",
    description="Get full details for a specific project."
)
async def get_project(
    project_id: str,
    current_user: CurrentUser = Depends(require_current_user),
) -> Any:
    """Get project by ID."""
    project = await require_owned_project(project_id, current_user)
    default_project_id = await get_user_default_project_id(current_user.user_id)

    return project_to_response(project, default_project_id=default_project_id)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project",
    description="Update project details, content directory, or config overrides."
)
async def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    current_user: CurrentUser = Depends(require_current_user),
) -> Any:
    """Update project details."""
    await require_owned_project(project_id, current_user)
    project = await project_store.update(
        project_id=project_id,
        name=request.name,
        url=str(request.github_url) if request.github_url else None,
        description=request.description,
        content_directories=request.content_directories,
        config_overrides=request.config_overrides,
        analytics_enabled=request.analytics_enabled,
    )

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    default_project_id = await get_user_default_project_id(current_user.user_id)
    return project_to_response(project, default_project_id=default_project_id)


@router.delete(
    "/{project_id}",
    summary="Delete project",
    description="Delete a project. This action cannot be undone."
)
async def delete_project(
    project_id: str,
    current_user: CurrentUser = Depends(require_current_user),
) -> dict:
    """Delete a project."""
    await require_owned_project(project_id, current_user)

    await project_store.delete(project_id)
    return {"deleted": True, "project_id": project_id}


@router.post(
    "/{project_id}/set-default",
    response_model=ProjectResponse,
    summary="Set default project",
    description="Set this project as the user's default project."
)
async def set_default_project(
    project_id: str,
    current_user: CurrentUser = Depends(require_current_user),
) -> Any:
    """Set project as default."""
    await require_owned_project(project_id, current_user)
    await user_data_store.update_user_settings(
        current_user.user_id,
        {"defaultProjectId": project_id},
    )
    project = await project_store.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project_to_response(project, default_project_id=project_id)


@router.post(
    "/{project_id}/refresh",
    response_model=ProjectDetectionResult,
    summary="Refresh project analysis",
    description="""
    Re-analyze the project repository.

    **What it does:**
    - Pulls latest changes from GitHub
    - Re-detects tech stack
    - Updates content directory detection
    - Preserves user config overrides

    Useful when the repository has changed.
    """
)
async def refresh_project(
    project_id: str,
    current_user: CurrentUser = Depends(require_current_user),
) -> ProjectDetectionResult:
    """Re-analyze project repository."""
    await require_owned_project(project_id, current_user)
    try:
        return await project_onboarding_service.refresh_analysis(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{project_id}/scan-content",
    summary="Scan and import content",
    description="""
    Scan the project's content directories and import all articles into the scheduling queue.

    **What it does:**
    - Reads `local_repo_path` and `content_directories` from project settings
    - Parses frontmatter (title, pubDate, draft, tags) from each markdown file
    - Creates a ContentRecord per article in the status queue
    - Already published articles → status `published`
    - Drafts or future-dated articles → status `pending_review`
    - Skips files already imported (deduplication by path)

    **Prerequisite:** Project must have been analyzed (`/analyze` + `/confirm`).
    """
)
async def scan_project_content(
    project_id: str,
    current_user: CurrentUser = Depends(require_current_user),
) -> dict:
    """Import all markdown content from the project into the scheduling queue."""
    await require_owned_project(project_id, current_user)
    scanner = get_content_scanner()
    result = await scanner.scan_project(project_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Scan failed"))
    return result


@router.post(
    "/{project_id}/propose-schedule",
    summary="AI scheduling proposal",
    description="""
    Groups pending articles by topical cluster and asks Claude to propose
    a strategic publication order.

    **Returns a proposal for user review — does NOT apply anything yet.**
    Call `/{project_id}/apply-schedule` to confirm.

    Query params:
    - `cadence`: articles per week (default: 5)
    - `start_date`: ISO date for first publication (default: tomorrow)
    """
)
async def propose_schedule(
    project_id: str,
    cadence: int = 5,
    start_date: Optional[str] = None,
    current_user: CurrentUser = Depends(require_current_user),
) -> dict:
    """Generate an AI-powered cluster scheduling proposal."""
    await require_owned_project(project_id, current_user)
    scheduler = get_cluster_scheduler()
    result = scheduler.propose(project_id, cadence_per_week=cadence, start_date=start_date)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Proposal failed"))
    return result


@router.post(
    "/{project_id}/apply-schedule",
    summary="Apply scheduling plan",
    description="""
    Applies a validated scheduling plan: assigns pubDates to all pending articles
    following the cluster order, and updates their metadata.

    Call this after reviewing the proposal from `propose-schedule`.

    Body (optional):
    - `cadence`: articles per week
    - `start_date`: ISO date string
    - `cluster_order`: list of cluster names in desired order (from the proposal)
    """
)
async def apply_schedule(
    project_id: str,
    cadence: int = 5,
    start_date: Optional[str] = None,
    cluster_order: Optional[list] = None,
    current_user: CurrentUser = Depends(require_current_user),
) -> dict:
    """Apply the validated schedule to all pending articles."""
    await require_owned_project(project_id, current_user)
    scheduler = get_cluster_scheduler()
    result = scheduler.apply_schedule(
        project_id,
        cadence_per_week=cadence,
        start_date=start_date,
        cluster_order=cluster_order,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Apply failed"))
    return result
