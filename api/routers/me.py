"""Authenticated account bootstrap endpoints."""

from fastapi import APIRouter, Depends

from agents.seo.config.project_store import project_store
from api.dependencies.auth import CurrentUser, require_current_user
from api.models.bootstrap import BootstrapResponse, MeResponse
from api.services.user_data_store import user_data_store

router = APIRouter(prefix="/api", tags=["Auth"])


@router.get("/me", response_model=MeResponse, summary="Get current authenticated user")
async def get_me(
    current_user: CurrentUser = Depends(require_current_user),
) -> MeResponse:
    """Return the current authenticated user and basic workspace presence."""
    projects = await project_store.get_by_user(current_user.user_id)
    settings = await user_data_store.get_user_settings(current_user.user_id)
    configured_default = settings.get("defaultProjectId")
    default_project_id = configured_default if any(
        project.id == configured_default for project in projects
    ) else (projects[0].id if projects else None)

    return MeResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        workspace_exists=bool(projects),
        default_project_id=default_project_id,
    )


@router.get(
    "/bootstrap",
    response_model=BootstrapResponse,
    summary="Get bootstrap state for app routing",
)
async def get_bootstrap(
    current_user: CurrentUser = Depends(require_current_user),
) -> BootstrapResponse:
    """Return the minimum authenticated bootstrap state needed by Flutter."""
    projects = await project_store.get_by_user(current_user.user_id)
    settings = await user_data_store.get_user_settings(current_user.user_id)
    configured_default = settings.get("defaultProjectId")
    default_project_id = configured_default if any(
        project.id == configured_default for project in projects
    ) else (projects[0].id if projects else None)

    user = MeResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        workspace_exists=bool(projects),
        default_project_id=default_project_id,
    )

    return BootstrapResponse(
        user=user,
        projects_count=len(projects),
        default_project_id=default_project_id,
        workspace_status="ready" if projects else "empty",
    )
