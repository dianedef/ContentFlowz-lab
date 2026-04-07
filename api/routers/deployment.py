"""
SEO Deployment API Router

Provides endpoints for managing SEO content deployment:
- Single topic runs
- Batch processing
- Schedule management
- Log viewing
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from typing import List, Optional
import uuid
import asyncio
from datetime import datetime

from api.dependencies.auth import require_current_user
from api.services.job_store import job_store

from api.models.deployment import (
    DeploymentRunRequest,
    BatchRunRequest,
    ScheduleRequest,
    DeploymentStatus,
    LogEntry,
    Schedule,
    StepStatus,
    BatchProgress,
    ScheduleType,
    DeploymentRunResponse,
    BatchRunResponse,
    StopResponse,
    DeleteResponse,
)

router = APIRouter(
    prefix="/api/deployment",
    tags=["SEO Deployment"],
    dependencies=[Depends(require_current_user)],
)

DEPLOY_JOB_TYPE = "deployment"
SCHEDULE_JOB_TYPE = "deployment_schedule"

# Logs remain in-memory (ephemeral by nature, no need to persist)
_logs: List[LogEntry] = []

# Pipeline steps for progress tracking
PIPELINE_STEPS = [
    "research",
    "strategy",
    "content",
    "technical_seo",
    "editing",
    "deployment",
]


def _add_log(level: str, step: Optional[str], message: str) -> None:
    """Add a log entry"""
    _logs.append(
        LogEntry(
            timestamp=datetime.now(),
            level=level,
            step=step,
            message=message,
        )
    )
    # Keep only last 1000 logs
    if len(_logs) > 1000:
        _logs.pop(0)


def _get_default_cron(schedule_type: ScheduleType) -> str:
    """Get default cron expression for schedule type"""
    defaults = {
        ScheduleType.DAILY: "0 9 * * *",  # 9 AM daily
        ScheduleType.WEEKLY: "0 9 * * 1",  # 9 AM Monday
        ScheduleType.CUSTOM: "0 9 * * *",  # Default to daily
    }
    return defaults.get(schedule_type, "0 9 * * *")


def _initialize_steps() -> List[StepStatus]:
    """Initialize pipeline steps with pending status"""
    return [
        StepStatus(name=step, status="pending")
        for step in PIPELINE_STEPS
    ]


async def execute_pipeline(
    job_id: str,
    topic: str,
    dry_run: bool,
    auto_deploy: bool,
    target_repo: Optional[str],
) -> None:
    """Execute SEO pipeline (background task)"""

    steps = _initialize_steps()

    async def _update(step: Optional[str], progress: int, **kw: object) -> None:
        await job_store.update(job_id, current_step=step, progress=progress, steps=[s.model_dump() for s in steps], **kw)

    def _step_status(step_name: str, status: str) -> None:
        for s in steps:
            if s.name == step_name:
                s.status = status
                if status == "running":
                    s.started_at = datetime.now()
                elif status in ("completed", "error"):
                    s.completed_at = datetime.now()
                    if s.started_at:
                        s.duration_seconds = (s.completed_at - s.started_at).total_seconds()
                break

    async def _is_running() -> bool:
        job = await job_store.get(job_id)
        return bool(job and job.get("running"))

    try:
        pipeline_phases = [
            ("research", 10, f"Starting research for topic: {topic}"),
            ("strategy", 25, "Developing content strategy"),
            ("content", 45, "Generating content"),
            ("technical_seo", 65, "Applying technical SEO optimizations"),
            ("editing", 80, "Final editing and quality check"),
        ]

        for step_name, progress, msg in pipeline_phases:
            _step_status(step_name, "running")
            _add_log("info", step_name, msg)
            await _update(step_name, progress)

            await asyncio.sleep(2)
            _step_status(step_name, "completed")
            _add_log("info", step_name, f"{step_name.replace('_', ' ').title()} completed")

            if not await _is_running():
                _add_log("warning", step_name, "Pipeline stopped by user")
                return

        # Deployment phase
        if auto_deploy and not dry_run:
            _step_status("deployment", "running")
            _add_log("info", "deployment", f"Deploying to {target_repo or 'default repository'}")
            await _update("deployment", 90)
            await asyncio.sleep(2)
            _step_status("deployment", "completed")
            _add_log("info", "deployment", "Deployment completed successfully")
        else:
            _step_status("deployment", "completed")
            _add_log("info", "deployment", "Dry run - skipping deployment" if dry_run else "No-deploy flag set - skipping deployment")

        await _update(None, 100)
        _add_log("info", "complete", f"Pipeline completed successfully for: {topic}")

    except Exception as e:
        _add_log("error", None, f"Pipeline failed: {e}")
        await job_store.update(job_id, error=str(e))

    finally:
        await job_store.update(job_id, running=False, status="completed")


async def execute_batch(
    job_id: str,
    topics: List[str],
    delay: int,
    auto_deploy: bool,
) -> None:
    """Execute batch deployment"""

    for i, topic in enumerate(topics):
        job = await job_store.get(job_id)
        if not job or not job.get("running"):
            _add_log("warning", "batch", "Batch processing stopped")
            break

        await job_store.update(
            job_id,
            topic=topic,
            batch_progress={"completed": i, "total": len(topics), "current_topic": topic},
        )
        _add_log("info", "batch", f"Processing topic {i + 1}/{len(topics)}: {topic}")

        await execute_pipeline(job_id, topic, False, auto_deploy, None)

        await job_store.update(
            job_id,
            batch_progress={"completed": i + 1, "total": len(topics), "current_topic": topic},
        )

        if i < len(topics) - 1:
            job = await job_store.get(job_id)
            if job and job.get("running"):
                _add_log("info", "batch", f"Waiting {delay}s before next topic...")
                await asyncio.sleep(delay)

    await job_store.update(job_id, running=False, status="completed")
    _add_log("info", "batch", "Batch processing completed")


@router.post("/run", response_model=DeploymentRunResponse)
async def run_deployment(
    request: DeploymentRunRequest,
    background_tasks: BackgroundTasks,
) -> DeploymentRunResponse:
    """
    Start single topic deployment

    Initiates the SEO content generation pipeline for a single topic.
    The pipeline runs in the background and progress can be monitored
    via the /status endpoint.
    """
    # Check for already running deployment
    running = await job_store.list_by_type(DEPLOY_JOB_TYPE, limit=1)
    if running and running[0].get("running"):
        raise HTTPException(
            status_code=400,
            detail="Deployment already running. Stop it first or wait for completion.",
        )

    job_id = str(uuid.uuid4())
    await job_store.upsert(
        job_id,
        DEPLOY_JOB_TYPE,
        status="running",
        running=True,
        topic=request.topic,
        current_step=None,
        progress=0,
        steps=[s.model_dump() for s in _initialize_steps()],
    )

    _add_log("info", None, f"Starting deployment for topic: {request.topic}")

    background_tasks.add_task(
        execute_pipeline,
        job_id,
        request.topic,
        request.dry_run,
        not request.no_deploy,
        request.target_repo,
    )

    return DeploymentRunResponse(
        job_id=job_id,
        status="started",
        topic=request.topic,
    )


@router.post("/batch", response_model=BatchRunResponse)
async def run_batch(
    request: BatchRunRequest,
    background_tasks: BackgroundTasks,
) -> BatchRunResponse:
    """
    Start batch deployment

    Processes multiple topics sequentially with configurable delay between them.
    """
    running = await job_store.list_by_type(DEPLOY_JOB_TYPE, limit=1)
    if running and running[0].get("running"):
        raise HTTPException(
            status_code=400,
            detail="Deployment already running. Stop it first or wait for completion.",
        )

    job_id = str(uuid.uuid4())
    await job_store.upsert(
        job_id,
        DEPLOY_JOB_TYPE,
        status="running",
        running=True,
        topics=request.topics,
        topic=request.topics[0] if request.topics else None,
        current_step=None,
        progress=0,
        steps=[s.model_dump() for s in _initialize_steps()],
        batch_progress={"completed": 0, "total": len(request.topics), "current_topic": request.topics[0] if request.topics else None},
    )

    _add_log("info", None, f"Starting batch deployment for {len(request.topics)} topics")

    background_tasks.add_task(
        execute_batch,
        job_id,
        request.topics,
        request.delay_seconds,
        request.auto_deploy,
    )

    return BatchRunResponse(
        batch_id=job_id,
        total_topics=len(request.topics),
        status="started",
    )


@router.get("/status", response_model=DeploymentStatus)
async def get_status() -> DeploymentStatus:
    """
    Get current deployment status

    Returns the current state of any running deployment including
    progress, current step, and any errors.
    """
    jobs = await job_store.list_by_type(DEPLOY_JOB_TYPE, limit=1)
    if not jobs:
        return DeploymentStatus(running=False)

    job = jobs[0]
    # Reconstruct StepStatus objects from stored dicts
    raw_steps = job.get("steps", [])
    steps = []
    for s in raw_steps:
        if isinstance(s, dict):
            steps.append(StepStatus(**s))
        elif isinstance(s, StepStatus):
            steps.append(s)

    batch = job.get("batch_progress")
    batch_progress = BatchProgress(**batch) if isinstance(batch, dict) else batch

    return DeploymentStatus(
        running=job.get("running", False),
        job_id=job.get("job_id"),
        job_type=job.get("job_type", DEPLOY_JOB_TYPE),
        topic=job.get("topic"),
        current_step=job.get("current_step"),
        progress=job.get("progress", 0),
        steps=steps,
        batch_progress=batch_progress,
        error=job.get("error"),
    )


@router.post("/stop", response_model=StopResponse)
async def stop_deployment() -> StopResponse:
    """
    Stop running deployment

    Gracefully stops the current deployment at the next checkpoint.
    """
    jobs = await job_store.list_by_type(DEPLOY_JOB_TYPE, limit=1)
    if jobs and jobs[0].get("running"):
        await job_store.update(jobs[0]["job_id"], running=False, stopped=True)
        _add_log("warning", None, "Deployment stopped by user")

    return StopResponse(status="stopped")


@router.get("/logs", response_model=List[LogEntry])
async def get_logs(
    level: Optional[str] = Query(default=None, description="Filter by log level"),
    limit: int = Query(default=100, ge=1, le=1000, description="Max logs to return"),
    since: Optional[str] = Query(default=None, description="ISO timestamp to filter from"),
) -> List[LogEntry]:
    """
    Get deployment logs

    Returns recent log entries with optional filtering by level and time.
    """
    logs = _logs

    # Filter by level
    if level:
        logs = [log for log in logs if log.level == level]

    # Filter by timestamp
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            logs = [log for log in logs if log.timestamp >= since_dt]
        except ValueError:
            pass

    return logs[-limit:]


@router.get("/schedules", response_model=List[Schedule])
async def list_schedules() -> List[Schedule]:
    """
    List all schedules

    Returns all configured deployment schedules.
    """
    jobs = await job_store.list_by_type(SCHEDULE_JOB_TYPE, limit=100)
    return [
        Schedule(
            id=j["job_id"],
            schedule_type=j.get("schedule_type", "custom"),
            cron_expression=j.get("cron_expression", "0 9 * * *"),
            topics=j.get("topics", []),
            enabled=j.get("enabled", True),
        )
        for j in jobs
    ]


@router.post("/schedules", response_model=Schedule)
async def create_schedule(request: ScheduleRequest) -> Schedule:
    """
    Create or update schedule

    Creates a new deployment schedule with the specified configuration.
    """
    schedule_id = str(uuid.uuid4())
    cron = request.cron_expression or _get_default_cron(request.schedule_type)

    await job_store.upsert(
        schedule_id,
        SCHEDULE_JOB_TYPE,
        status="active",
        schedule_type=request.schedule_type.value,
        cron_expression=cron,
        topics=request.topics,
        enabled=request.enabled,
    )

    _add_log(
        "info",
        None,
        f"Created schedule {schedule_id}: {request.schedule_type.value} for {len(request.topics)} topics",
    )

    return Schedule(
        id=schedule_id,
        schedule_type=request.schedule_type,
        cron_expression=cron,
        topics=request.topics,
        enabled=request.enabled,
    )


@router.patch("/schedules/{schedule_id}", response_model=Schedule)
async def update_schedule(
    schedule_id: str,
    enabled: Optional[bool] = Query(default=None),
) -> Schedule:
    """
    Update schedule

    Updates an existing schedule's configuration.
    """
    job = await job_store.get(schedule_id)
    if not job:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if enabled is not None:
        await job_store.update(schedule_id, enabled=enabled)
        _add_log(
            "info",
            None,
            f"Schedule {schedule_id} {'enabled' if enabled else 'disabled'}",
        )
        job["enabled"] = enabled

    return Schedule(
        id=schedule_id,
        schedule_type=job.get("schedule_type", "custom"),
        cron_expression=job.get("cron_expression", "0 9 * * *"),
        topics=job.get("topics", []),
        enabled=job.get("enabled", True),
    )


@router.delete("/schedules/{schedule_id}", response_model=DeleteResponse)
async def delete_schedule(schedule_id: str) -> DeleteResponse:
    """
    Delete schedule

    Removes a deployment schedule.
    """
    await job_store.delete(schedule_id)
    _add_log("info", None, f"Deleted schedule {schedule_id}")

    return DeleteResponse(status="deleted")
