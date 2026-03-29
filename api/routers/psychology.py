"""Psychology Engine API Router

Exposes CrewAI agents for narrative synthesis, persona refinement,
and content angle generation. Uses background tasks for long-running
agent operations with polling-based status retrieval.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from api.dependencies.auth import CurrentUser, require_current_user
from api.models.psychology import (
    NarrativeSynthesisRequest,
    NarrativeSynthesisResult,
    PersonaRefinementRequest,
    AngleGenerationRequest,
    ContentAngleResult,
    AngleSelectionInput,
    MultiFormatExtract,
    PipelineDispatchRequest,
    PipelineDispatchResult,
)
import json
import uuid
import time

router = APIRouter(prefix="/api/psychology", tags=["Psychology Engine"])

# In-memory task tracking (production would use Redis/DB)
_tasks: dict[str, dict] = {}


def _set_task(task_id: str, status: str, result: dict | None = None):
    _tasks[task_id] = {
        "status": status,
        "result": result,
        "updated_at": time.time(),
    }


# ─────────────────────────────────────────────────
# Narrative Synthesis (Creator Brain)
# ─────────────────────────────────────────────────

def _run_synthesis_task(task_id: str, request: NarrativeSynthesisRequest):
    """Background task: run Creator Psychologist agent"""
    try:
        from agents.psychology.creator_psychologist import run_narrative_synthesis

        result = run_narrative_synthesis(
            profile_id=request.profile_id,
            entries=[{"content": eid, "entryType": "reflection"} for eid in request.entry_ids],
            current_voice=request.current_voice,
            current_positioning=request.current_positioning,
            chapter_title=request.chapter_title,
        )
        _set_task(task_id, "completed", result)
    except Exception as e:
        _set_task(task_id, "failed", {"error": str(e)})


@router.post("/synthesize-narrative")
async def synthesize_narrative(
    request: NarrativeSynthesisRequest,
    background_tasks: BackgroundTasks,
):
    """Trigger narrative synthesis from creator entries (async)."""
    task_id = str(uuid.uuid4())
    _set_task(task_id, "running")
    background_tasks.add_task(_run_synthesis_task, task_id, request)
    return {"task_id": task_id, "status": "running"}


@router.get("/synthesis-status/{task_id}")
async def get_synthesis_status(task_id: str):
    """Poll for narrative synthesis result."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# ─────────────────────────────────────────────────
# Persona Refinement (Customer Brain)
# ─────────────────────────────────────────────────

def _run_refinement_task(task_id: str, request: PersonaRefinementRequest):
    """Background task: run Audience Analyst agent"""
    try:
        from agents.psychology.audience_analyst import run_persona_refinement

        result = run_persona_refinement(
            persona=request.current_persona,
            analytics_data=request.analytics_data,
            content_performance=request.content_performance,
        )
        _set_task(task_id, "completed", result)
    except Exception as e:
        _set_task(task_id, "failed", {"error": str(e)})


@router.post("/refine-persona")
async def refine_persona(
    request: PersonaRefinementRequest,
    background_tasks: BackgroundTasks,
):
    """Trigger persona refinement using analytics data (async)."""
    task_id = str(uuid.uuid4())
    _set_task(task_id, "running")
    background_tasks.add_task(_run_refinement_task, task_id, request)
    return {"task_id": task_id, "status": "running"}


# ─────────────────────────────────────────────────
# Angle Generation (The Bridge)
# ─────────────────────────────────────────────────

def _run_angle_task(task_id: str, request: AngleGenerationRequest):
    """Background task: run Angle Strategist agent"""
    try:
        from agents.psychology.angle_strategist import run_angle_generation

        result = run_angle_generation(
            creator_voice=request.creator_voice,
            creator_positioning=request.creator_positioning,
            narrative_summary=request.narrative_summary,
            persona_data=request.persona_data,
            content_type=request.content_type.value if request.content_type else None,
            count=request.count,
            seo_signals=request.seo_signals,
            trending_signals=request.trending_signals,
        )
        _set_task(task_id, "completed", result)
    except Exception as e:
        _set_task(task_id, "failed", {"error": str(e)})


@router.post("/generate-angles")
async def generate_angles(
    request: AngleGenerationRequest,
    background_tasks: BackgroundTasks,
):
    """Trigger content angle generation (async)."""
    task_id = str(uuid.uuid4())
    _set_task(task_id, "running")
    background_tasks.add_task(_run_angle_task, task_id, request)
    return {"task_id": task_id, "status": "running"}


@router.get("/angles-status/{task_id}")
async def get_angles_status(task_id: str):
    """Poll for angle generation result."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# ─────────────────────────────────────────────────
# Multi-Format Render
# ─────────────────────────────────────────────────

@router.post("/render-extract", response_model=MultiFormatExtract, deprecated=True)
async def render_extract(
    request: AngleSelectionInput,
):
    """Deprecated — use POST /api/psychology/dispatch-pipeline instead.
    Returns static placeholder text.
    """
    return MultiFormatExtract(
        angle_id=request.angle_id,
        article_outline=f"# Article based on angle {request.angle_id}\n\n## Introduction\n...\n## Main Points\n...\n## Conclusion\n...",
        newsletter_hook=f"This week, something clicked...",
        social_post=f"Thread: Here's what I learned...",
        video_script_opener=f"Hey, today I want to share...",
    )


# ─────────────────────────────────────────────────
# Pipeline Dispatch (replaces render-extract)
# ─────────────────────────────────────────────────

# Format → (content_type, source_robot)
_FORMAT_MAP = {
    "article": ("article", "seo"),
    "newsletter": ("newsletter", "newsletter"),
    "short": ("short", "short"),
    "social_post": ("social_post", "social"),
}


def _run_pipeline_task(
    task_id: str,
    content_record_id: str,
    request: PipelineDispatchRequest,
):
    """Background task: dispatch to the appropriate content pipeline."""
    try:
        from status import get_status_service
        svc = get_status_service()

        fmt = request.target_format
        angle = request.angle_data
        voice = request.creator_voice or {}
        body = ""

        # Load project memory context to avoid duplicate topics
        existing_content_context = ""
        try:
            from memory.memory_service import get_memory_service
            mem = get_memory_service()
            existing_content_context = mem.load_project_context(
                query=angle.get("title", ""),
                user_id=getattr(request, '_user_id', None),
                project_id=request.project_id,
                limit=10,
            )
        except Exception:
            pass  # Memory service is optional

        if fmt == "article":
            from agents.seo.seo_crew import SEOContentCrew
            crew = SEOContentCrew()
            brand_voice_str = json.dumps(voice) if voice else None
            if existing_content_context and brand_voice_str:
                brand_voice_str += f"\n\n{existing_content_context}"
            result = crew.generate_content(
                target_keyword=request.seo_keyword or angle.get("title", ""),
                brand_voice=brand_voice_str,
                word_count=2500,
            )
            body = result.get("outputs", {}).get("article", str(result))

        elif fmt == "newsletter":
            from agents.newsletter.newsletter_crew import NewsletterCrew
            crew = NewsletterCrew()
            result = crew.generate_newsletter(
                topics=[angle.get("title", "")],
                target_audience=angle.get("pain_point_addressed", "general"),
            )
            body = result.get("html", "") or result.get("content", str(result))

        elif fmt == "short":
            from agents.short.short_crew import ShortContentCrew
            crew = ShortContentCrew()
            result = crew.generate_short(
                angle=angle,
                creator_voice=voice,
                project_id=request.project_id,
            )
            body = result.get("script", str(result))

        elif fmt == "social_post":
            from agents.social.social_crew import SocialPostCrew
            crew = SocialPostCrew()
            result = crew.generate_social_post(
                angle=angle,
                creator_voice=voice,
                project_id=request.project_id,
            )
            posts = result.get("posts", [])
            body = json.dumps(posts, indent=2) if posts else str(result)

        else:
            raise ValueError(f"Unknown format: {fmt}")

        # Save body and transition to pending_review
        if body:
            svc.save_content_body(content_record_id, body, edited_by=f"{fmt}_pipeline")
        svc.transition(content_record_id, "pending_review", f"{fmt}_pipeline")

        # Post-generation: mark source ideas as 'used'
        source_idea_ids = request.angle_data.get("source_idea_ids", [])
        for idea_id in source_idea_ids:
            try:
                svc.update_idea(idea_id, status="used")
            except Exception:
                pass

        # Memory integration: record generation for semantic dedup (scoped)
        try:
            from memory.memory_service import get_memory_service
            mem = get_memory_service()
            mem.store_generation_scoped(
                content_type=fmt,
                title=request.angle_data.get("title", ""),
                user_id=getattr(request, '_user_id', None),
                project_id=request.project_id,
                topics=request.angle_data.get("topics", []),
                summary=body[:200] if body else "",
                seo_keyword=request.seo_keyword,
                source=request.angle_data.get("source"),
            )
        except Exception:
            pass  # Memory service is optional

        _set_task(task_id, "completed", {
            "content_record_id": content_record_id,
            "format": fmt,
            "preview": body[:500] if body else None,
        })

    except Exception as e:
        _set_task(task_id, "failed", {"error": str(e), "content_record_id": content_record_id})
        # Try to mark the content record as failed
        try:
            from status import get_status_service
            svc = get_status_service()
            svc.transition(content_record_id, "failed", f"{request.target_format}_pipeline",
                           reason=str(e))
        except Exception:
            pass


@router.post("/dispatch-pipeline", response_model=PipelineDispatchResult)
async def dispatch_pipeline(
    request: PipelineDispatchRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_current_user),
):
    """Dispatch an angle to a content generation pipeline (async).

    Replaces the deprecated render-extract endpoint with real content generation.
    Checks for duplicate content before creating. Creates a ContentRecord and
    launches the appropriate pipeline in the background.
    """
    fmt = request.target_format
    if fmt not in _FORMAT_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown format '{fmt}'. Valid: {list(_FORMAT_MAP.keys())}",
        )

    content_type, source_robot = _FORMAT_MAP[fmt]
    task_id = str(uuid.uuid4())
    title = request.angle_data.get("title", f"Untitled {fmt}")

    # Pre-generation dedup check
    from utils.dedup import check_content_duplicate
    duplicate = check_content_duplicate(
        title=title,
        user_id=current_user.user_id,
        project_id=request.project_id,
    )
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"Similar content already exists: '{duplicate['title']}' (status: {duplicate['status']})",
                "existing_content_id": duplicate["id"],
                "existing_title": duplicate["title"],
            },
        )

    # Create content record
    try:
        from status import get_status_service
        svc = get_status_service()
        record = svc.create_content(
            title=title,
            content_type=content_type,
            source_robot=source_robot,
            status="in_progress",
            project_id=request.project_id,
            user_id=current_user.user_id,
            tags=[fmt],
            metadata={
                "angle": request.angle_data,
                "pipeline_task_id": task_id,
                "seo_keyword": request.seo_keyword,
                "seo_signals": request.angle_data.get("seo_signals"),
                "source_idea_ids": request.angle_data.get("source_idea_ids", []),
                "source_idea_source": request.angle_data.get("source"),
            },
        )
        content_record_id = record.id
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create content record: {e}")

    _set_task(task_id, "running")
    background_tasks.add_task(_run_pipeline_task, task_id, content_record_id, request)

    return PipelineDispatchResult(
        task_id=task_id,
        content_record_id=content_record_id,
        format=fmt,
        status="running",
    )


@router.get("/pipeline-status/{task_id}")
async def get_pipeline_status(task_id: str):
    """Poll for pipeline dispatch result."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
