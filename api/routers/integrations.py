"""Integration endpoints (GitHub OAuth + repository browsing)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
import httpx
import os

from api.dependencies.auth import CurrentUser, require_current_user
from api.services.user_data_store import user_data_store


router = APIRouter(
    prefix="/api/integrations/github",
    tags=["Integrations"],
    responses={404: {"description": "Not found"}},
)

GITHUB_OAUTH_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_OAUTH_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_URL = "https://api.github.com"
GITHUB_SCOPE = "repo"


def _github_client_id() -> str:
    value = os.getenv("GITHUB_CLIENT_ID")
    if not value:
        raise HTTPException(
            status_code=503,
            detail="GitHub OAuth is not configured: missing GITHUB_CLIENT_ID.",
        )
    return value


def _github_client_secret() -> str:
    value = os.getenv("GITHUB_CLIENT_SECRET")
    if not value:
        raise HTTPException(
            status_code=503,
            detail="GitHub OAuth is not configured: missing GITHUB_CLIENT_SECRET.",
        )
    return value


def _github_scopes() -> str:
    return os.getenv("GITHUB_OAUTH_SCOPES", GITHUB_SCOPE)


def _github_redirect_uri(request: Request) -> str:
    override = (os.getenv("GITHUB_OAUTH_REDIRECT_URI") or "").strip()
    if override:
        return override
    return str(request.url_for("github_oauth_callback"))


def _raise_store_error(exc: RuntimeError) -> None:
    raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/connect")
async def github_connect(
    request: Request,
    current_user: CurrentUser = Depends(require_current_user),
) -> dict[str, str]:
    """Return the GitHub authorization URL for this user."""
    client_id = _github_client_id()
    try:
        state = await user_data_store.create_github_oauth_state(current_user.user_id)
    except RuntimeError as exc:
        _raise_store_error(exc)
    return {
        "connect_url": (
            f"{GITHUB_OAUTH_AUTHORIZE_URL}"
            f"?client_id={client_id}"
            f"&scope={_github_scopes()}"
            f"&state={state}"
            f"&redirect_uri={_github_redirect_uri(request)}"
        ),
    }


@router.get("/callback", name="github_oauth_callback")
async def github_callback(
    code: str = Query(...),
    state: str = Query(...),
) -> dict[str, Any]:
    """Exchange OAuth code for token and store the GitHub connection."""
    try:
        user_id = await user_data_store.consume_github_oauth_state(state)
    except RuntimeError as exc:
        _raise_store_error(exc)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    payload = {
        "client_id": _github_client_id(),
        "client_secret": _github_client_secret(),
        "code": code,
    }

    headers = {"Accept": "application/json"}

    async with httpx.AsyncClient(timeout=20.0) as client:
        token_resp = await client.post(
            GITHUB_OAUTH_TOKEN_URL,
            data=payload,
            headers=headers,
        )
        if token_resp.status_code >= 400:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to exchange OAuth code: {token_resp.text}",
            )
        token_payload = token_resp.json()

        access_token = token_payload.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=400,
                detail="OAuth callback did not return an access token.",
            )
        scopes = (
            token_payload.get("scope")
            or token_resp.headers.get("X-Oauth-Scopes", "")
        )
        scopes_list = [scope.strip() for scope in scopes.split(",") if scope.strip()]

        user_resp = await client.get(
            f"{GITHUB_API_URL}/user",
            headers={"Authorization": f"token {access_token}"},
        )
        if user_resp.status_code >= 400:
            raise HTTPException(
                status_code=400,
                detail="OAuth token is invalid or revoked.",
            )

        user_payload = user_resp.json()
        try:
            await user_data_store.upsert_github_integration(
                user_id=user_id,
                token=access_token,
                github_user_id=(user_payload.get("id") and str(user_payload["id"])),
                github_username=user_payload.get("login"),
                scopes=scopes_list,
            )
        except RuntimeError as exc:
            _raise_store_error(exc)

        return {
            "connected": True,
            "github_user_id": user_payload.get("id"),
            "github_username": user_payload.get("login"),
            "scope": scopes_list,
            "message": "GitHub connected successfully. You can return to the app.",
        }


@router.get("/status")
async def github_status(
    current_user: CurrentUser = Depends(require_current_user),
) -> dict[str, Any]:
    """Return whether GitHub is connected and its basic metadata."""
    try:
        integration = await user_data_store.get_github_integration(current_user.user_id)
    except RuntimeError as exc:
        _raise_store_error(exc)
    if not integration:
        return {"connected": False}

    return {
        "connected": True,
        "github_username": integration.get("githubUsername"),
        "github_user_id": integration.get("githubUserId"),
        "scope": integration.get("scopes"),
    }


@router.delete("/disconnect")
async def github_disconnect(
    current_user: CurrentUser = Depends(require_current_user),
) -> dict[str, Any]:
    """Disconnect GitHub integration for current user."""
    try:
        await user_data_store.delete_github_integration(current_user.user_id)
    except RuntimeError as exc:
        _raise_store_error(exc)
    return {"connected": False}


@router.get("/repos")
async def github_repos(
    current_user: CurrentUser = Depends(require_current_user),
    query: Optional[str] = None,
    per_page: int = 100,
    page: int = 1,
) -> dict[str, Any]:
    """List repos visible with the current GitHub token."""
    try:
        integration = await user_data_store.get_github_integration(current_user.user_id)
    except RuntimeError as exc:
        _raise_store_error(exc)
    if not integration:
        raise HTTPException(status_code=401, detail="GitHub is not connected.")

    token = integration.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="GitHub token is missing.")

    params = {
        "per_page": max(1, min(per_page, 100)),
        "page": max(1, page),
        "sort": "updated",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{GITHUB_API_URL}/user/repos",
            params=params,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
            },
        )
        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="GitHub token is invalid.")
        if response.status_code >= 400:
            raise HTTPException(
                status_code=400,
                detail=f"Unable to load repositories: {response.text}",
            )

        repos = response.json() if isinstance(response.json(), list) else []
        if not query:
            return {"repos": repos}

        lowered = query.strip().lower()
        return {
            "repos": [
                repo
                for repo in repos
                if isinstance(repo, dict)
                and (
                    lowered in str(repo.get("full_name", "")).lower()
                    or lowered in str(repo.get("name", "")).lower()
                )
            ]
        }


@router.get("/repo-tree")
async def github_repo_tree(
    current_user: CurrentUser = Depends(require_current_user),
    owner: str = Query(...),
    repo: str = Query(...),
    path: str = Query(""),
) -> dict[str, Any]:
    """Browse repository folders from the current authenticated GitHub account."""
    try:
        integration = await user_data_store.get_github_integration(current_user.user_id)
    except RuntimeError as exc:
        _raise_store_error(exc)
    if not integration:
        raise HTTPException(status_code=401, detail="GitHub is not connected.")

    token = integration.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="GitHub token is missing.")

    clean_path = path.strip().lstrip("/")
    normalized_path = clean_path if clean_path else ""

    async with httpx.AsyncClient(timeout=20.0) as client:
        if normalized_path:
            response = await client.get(
                f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents/{normalized_path}",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
        else:
            response = await client.get(
                f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github+json",
                },
            )

        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="GitHub token is invalid.")
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Repository or path not found.")
        if response.status_code >= 400:
            raise HTTPException(
                status_code=400,
                detail=f"Unable to fetch repository tree: {response.text}",
            )

        items = response.json()
        if isinstance(items, dict):
            items = [items]

        if not isinstance(items, list):
            raise HTTPException(
                status_code=400,
                detail="Unexpected GitHub response for repository contents.",
            )

        directories = [
            {
                "name": entry.get("name"),
                "path": entry.get("path", ""),
                "has_markdown_files": False,
            }
            for entry in items
            if isinstance(entry, dict)
            and entry.get("type") == "dir"
            and entry.get("name")
        ]

        return {
            "repository": f"{owner}/{repo}",
            "current_path": normalized_path,
            "directories": directories,
        }
