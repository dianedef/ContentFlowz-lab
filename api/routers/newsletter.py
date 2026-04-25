"""Newsletter generation and management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from api.dependencies.auth import CurrentUser, require_current_user
from api.services.job_store import job_store
from api.services.ai_runtime_service import AIRuntimeServiceError, ai_runtime_service
from api.services.user_key_store import user_key_store  # backward-compatible test hook
from api.services.user_llm_service import (
    NEWSLETTER_OPENROUTER_MODEL,
    AIRuntimeResolutionError,
    UserLLMCredentialError,
    user_llm_service,
)

router = APIRouter(
    prefix="/api/newsletter",
    tags=["Newsletter"],
    dependencies=[Depends(require_current_user)],
)


def _raise_runtime_http(exc: Exception) -> None:
    if isinstance(exc, AIRuntimeServiceError):
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    if isinstance(exc, AIRuntimeResolutionError):
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    if isinstance(exc, UserLLMCredentialError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail=str(exc)) from exc


def _dependency_error_email_backend_missing(*, include_email_insights: bool) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "code": "newsletter_email_backend_missing",
            "message": "Email insights require IMAP or Composio to be configured.",
            "kind": "dependency",
            "route": "newsletter.generate",
            "retryable": False,
            "details": {
                "includeEmailInsights": include_email_insights,
                "requiredAnyOf": ["imap", "composio"],
            },
        },
    )


class NewsletterRequest(BaseModel):
    """Request to generate a newsletter."""

    name: str = Field(..., description="Newsletter name/title")
    topics: List[str] = Field(..., description="Topics to cover")
    target_audience: str = Field(..., description="Target audience description")
    tone: str = Field(default="professional", description="Writing tone")
    competitor_emails: List[str] = Field(
        default_factory=list,
        description="Competitor newsletter emails to analyze"
    )
    include_email_insights: bool = Field(
        default=True,
        description="Read Gmail for insights"
    )
    max_sections: int = Field(default=5, description="Max content sections")


class NewsletterResponse(BaseModel):
    """Response with generated newsletter."""

    success: bool
    newsletter_id: str
    subject_line: str
    preview_text: str
    word_count: int
    read_time_minutes: int
    content: str
    sections: List[Dict[str, Any]]
    sources: Dict[str, List[str]]
    created_at: datetime


class NewsletterStatus(BaseModel):
    """Status of newsletter generation job."""

    job_id: str
    status: str  # pending, running, completed, failed
    progress: int  # 0-100
    message: Optional[str] = None
    result: Optional[NewsletterResponse] = None
    error: Optional[str] = None


def _build_newsletter_config(request: NewsletterRequest):
    from agents.newsletter.schemas.newsletter_schemas import (
        NewsletterConfig,
        NewsletterTone,
    )

    tone_map = {
        "professional": NewsletterTone.PROFESSIONAL,
        "casual": NewsletterTone.CASUAL,
        "friendly": NewsletterTone.FRIENDLY,
        "educational": NewsletterTone.EDUCATIONAL,
        "promotional": NewsletterTone.PROMOTIONAL,
        "technical": NewsletterTone.EDUCATIONAL,
        "inspirational": NewsletterTone.FRIENDLY,
    }

    return NewsletterConfig(
        name=request.name,
        topics=request.topics,
        target_audience=request.target_audience,
        tone=tone_map.get(request.tone, NewsletterTone.PROFESSIONAL),
        competitor_emails=request.competitor_emails,
        include_email_insights=request.include_email_insights,
        max_sections=request.max_sections,
    )


def _newsletter_response_from_result(result: Dict[str, Any]) -> NewsletterResponse:
    draft = result.get("draft", {})

    return NewsletterResponse(
        success=True,
        newsletter_id=f"nl_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        subject_line=draft.get("subject_line", "Newsletter"),
        preview_text=draft.get("preview_text", ""),
        word_count=draft.get("word_count", 0),
        read_time_minutes=draft.get("estimated_read_time", 1),
        content=draft.get("plain_text", ""),
        sections=draft.get("sections", []),
        sources={
            "emails": draft.get("email_sources", []),
            "web": draft.get("web_sources", []),
        },
        created_at=datetime.now(),
    )


async def _get_owned_newsletter_job(job_id: str, user_id: str) -> dict[str, Any]:
    job = await job_store.get(job_id)
    if not job or job.get("job_type") != "newsletter.generate":
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if job.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@router.post(
    "/generate",
    response_model=NewsletterResponse,
    summary="Generate newsletter",
    description="Generate a newsletter using AI agents with Gmail and web research"
)
async def generate_newsletter(
    request: NewsletterRequest,
    current_user: CurrentUser = Depends(require_current_user),
):
    """
    Generate a newsletter synchronously.

    This endpoint:
    1. Reads recent emails via Composio Gmail integration
    2. Analyzes competitor newsletters
    3. Researches trending topics via Exa AI
    4. Generates newsletter content

    Requires:
    - Composio Gmail authentication: `composio add gmail`
    - EXA_API_KEY environment variable
    """
    route_id = "newsletter.generate"
    try:
        resolution = await ai_runtime_service.preflight_providers(
            user_id=current_user.user_id,
            route=route_id,
            required_providers=["openrouter", "exa"],
        )
    except Exception as exc:
        _raise_runtime_http(exc)

    from agents.newsletter.config.newsletter_config import validate_config

    checks = validate_config(
        openrouter_configured=True,
        exa_configured=True,
    )
    email_backend_ready = bool(
        checks.get("imap_configured") or checks.get("composio_configured")
    )
    if request.include_email_insights and not email_backend_ready:
        raise _dependency_error_email_backend_missing(
            include_email_insights=request.include_email_insights
        )

    try:
        from agents.newsletter.newsletter_crew import NewsletterCrew

        with ai_runtime_service.bind_provider_env(resolution):
            llm = await user_llm_service.get_crewai_llm(
                current_user.user_id,
                model=NEWSLETTER_OPENROUTER_MODEL,
                route=route_id,
            )
            config = _build_newsletter_config(request)
            crew = NewsletterCrew(
                llm_model=llm,
                use_gmail=request.include_email_insights,
            )
            result = crew.generate_newsletter(config, user_id=current_user.user_id)
            return _newsletter_response_from_result(result)
    except (AIRuntimeResolutionError, AIRuntimeServiceError, UserLLMCredentialError) as exc:
        _raise_runtime_http(exc)
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Newsletter agents not available: {str(e)}. "
                   f"Install with: pip install composio-crewai"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Newsletter generation failed: {str(e)}"
        )


@router.post(
    "/generate-async",
    response_model=NewsletterStatus,
    summary="Generate newsletter (async)",
    description="Start newsletter generation as background job"
)
@router.post(
    "/generate/async",
    response_model=NewsletterStatus,
    summary="Generate newsletter (async)",
    description="Start newsletter generation as background job"
)
async def generate_newsletter_async(
    request: NewsletterRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_current_user),
):
    """
    Start newsletter generation as a background job.

    Returns immediately with a job ID. Poll /newsletter/status/{job_id}
    to check progress and retrieve results.
    """
    route_id = "newsletter.generate"
    try:
        resolution = await ai_runtime_service.preflight_providers(
            user_id=current_user.user_id,
            route=route_id,
            required_providers=["openrouter", "exa"],
        )
    except Exception as exc:
        _raise_runtime_http(exc)

    from agents.newsletter.config.newsletter_config import validate_config

    checks = validate_config(
        openrouter_configured=True,
        exa_configured=True,
    )
    email_backend_ready = bool(
        checks.get("imap_configured") or checks.get("composio_configured")
    )
    if request.include_email_insights and not email_backend_ready:
        raise _dependency_error_email_backend_missing(
            include_email_insights=request.include_email_insights
        )

    job_id = str(uuid.uuid4())[:8]

    await job_store.upsert(
        job_id=job_id,
        job_type="newsletter.generate",
        status="pending",
        progress=0,
        message="Job queued",
        user_id=current_user.user_id,
        result=None,
        error=None,
    )

    async def run_generation():
        try:
            await job_store.update(
                job_id,
                status="running",
                progress=10,
                message="Initializing agents...",
                error=None,
            )

            from agents.newsletter.newsletter_crew import NewsletterCrew
            with ai_runtime_service.bind_provider_env(resolution):
                llm = await user_llm_service.get_crewai_llm(
                    current_user.user_id,
                    model=NEWSLETTER_OPENROUTER_MODEL,
                    route=route_id,
                )
                await job_store.update(job_id, progress=20, message="Reading emails...")

                config = _build_newsletter_config(request)

                await job_store.update(job_id, progress=40, message="Researching content...")

                crew = NewsletterCrew(
                    llm_model=llm,
                    use_gmail=request.include_email_insights,
                )
                result = crew.generate_newsletter(
                    config,
                    user_id=current_user.user_id,
                )

            await job_store.update(job_id, progress=90, message="Finalizing...")

            response_payload = _newsletter_response_from_result(result)
            await job_store.update(
                job_id,
                status="completed",
                progress=100,
                message="Newsletter generated successfully",
                result=response_payload.model_dump(mode="json"),
                error=None,
            )

        except Exception as e:
            await job_store.update(
                job_id,
                status="failed",
                progress=100,
                message="Newsletter generation failed",
                error=str(e),
            )

    background_tasks.add_task(run_generation)

    return NewsletterStatus(
        job_id=job_id,
        status="pending",
        progress=0,
        message="Job queued",
    )


@router.get(
    "/jobs/{job_id}",
    response_model=NewsletterStatus,
    summary="Get job status",
    description="Check status of async newsletter generation"
)
@router.get(
    "/status/{job_id}",
    response_model=NewsletterStatus,
    summary="Get job status",
    description="Check status of async newsletter generation"
)
async def get_job_status(
    job_id: str,
    current_user: CurrentUser = Depends(require_current_user),
):
    """Get the status of a newsletter generation job."""
    job = await _get_owned_newsletter_job(job_id, current_user.user_id)

    return NewsletterStatus(
        job_id=job["job_id"],
        status=job["status"],
        progress=job.get("progress", 0),
        message=job.get("message"),
        result=NewsletterResponse(**job["result"]) if job.get("result") else None,
        error=job.get("error"),
    )


@router.get(
    "/config/check",
    summary="Check configuration",
    description="Verify newsletter dependencies are configured"
)
async def check_config(
    include_email_insights: bool = Query(default=True),
    current_user: CurrentUser = Depends(require_current_user),
):
    """Check if all newsletter dependencies are configured."""
    from agents.newsletter.config.newsletter_config import validate_config

    async def _provider_ready(provider: str) -> bool:
        try:
            await ai_runtime_service.preflight_providers(
                user_id=current_user.user_id,
                route="newsletter.generate",
                required_providers=[provider],
            )
            return True
        except AIRuntimeServiceError:
            return False
        except AIRuntimeResolutionError:
            return False
        except UserLLMCredentialError:
            return False

    openrouter_ready = await _provider_ready("openrouter")
    exa_ready = await _provider_ready("exa")
    checks = validate_config(
        openrouter_configured=openrouter_ready,
        exa_configured=exa_ready,
    )
    llm_configured = bool(openrouter_ready and exa_ready)
    if include_email_insights:
        server_ready = bool(checks.get("imap_configured") or checks.get("composio_configured"))
    else:
        server_ready = True

    return {
        "configured": bool(llm_configured and server_ready),
        "ready": bool(llm_configured and server_ready),
        "llm_configured": llm_configured,
        "server_ready": server_ready,
        "checks": checks,
        "instructions": {
            "composio": "Run: composio add gmail",
            "exa": "Set EXA_API_KEY in environment",
            "sendgrid": "Set SENDGRID_API_KEY for sending",
        }
    }


class SenderInfo(BaseModel):
    """Information about an email sender found in inbox."""

    from_email: str = Field(..., description="Sender email address")
    from_name: str = Field(default="", description="Sender display name")
    email_count: int = Field(default=1, description="Number of emails from this sender")
    is_newsletter: bool = Field(default=False, description="Detected as newsletter")
    latest_subject: str = Field(default="", description="Most recent email subject")
    latest_date: Optional[str] = Field(default=None, description="Most recent email date")


class SenderListResponse(BaseModel):
    """Response with list of senders from inbox scan."""

    senders: List[SenderInfo]
    total_scanned: int = Field(default=0, description="Total emails scanned")
    scan_days: int = Field(default=30, description="Days back scanned")


@router.get(
    "/senders",
    response_model=SenderListResponse,
    summary="Scan inbox senders",
    description="Scan Gmail inbox and return grouped sender list with newsletter detection"
)
async def get_inbox_senders(
    days_back: int = Query(default=30, ge=1, le=90, description="Days back to scan"),
    max_results: int = Query(default=200, ge=10, le=500, description="Max emails to scan"),
    folder: str = Query(default="INBOX", description="Folder to scan"),
    newsletters_only: bool = Query(default=True, description="Only return newsletter senders"),
):
    """
    Scan Gmail inbox via IMAP and return a list of unique senders.

    Groups by sender email, counts occurrences, detects newsletters.
    Uses headers_only=True for speed (no body download).
    """
    try:
        from agents.newsletter.tools.imap_tools import IMAPNewsletterReader

        reader = IMAPNewsletterReader()
        senders, total_scanned = reader.fetch_senders_from_inbox(
            days_back=days_back,
            max_results=max_results,
            folder=folder,
            newsletters_only=newsletters_only,
        )

        return SenderListResponse(
            senders=[SenderInfo(**s) for s in senders],
            total_scanned=total_scanned,
            scan_days=days_back,
        )

    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"IMAP tools not available: {str(e)}. Install with: pip install imap-tools"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Configuration error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Inbox scan failed: {str(e)}"
        )
