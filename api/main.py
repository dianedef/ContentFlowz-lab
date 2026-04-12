"""
SEO Robots FastAPI Server

Production-grade API server exposing Python SEO agents to Next.js dashboard.
Uses FastAPI 0.128.0 (latest) with modern best practices.

Architecture:
- REST API for synchronous operations
- WebSocket for real-time streaming
- Dependency injection for agents
- Auto-generated OpenAPI docs
- CORS enabled for Next.js frontend

Run with:
    uvicorn api.main:app --reload --port 8000

Docs:
    http://localhost:8000/docs (Swagger UI)
    http://localhost:8000/redoc (ReDoc)
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
import os
import time
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.routers import mesh_router, research_router, health_router, projects_router, newsletter_router, deployment_router, images_router, status_router, reels_router, psychology_router, me_router, settings_router, creator_profile_router, personas_router, idea_pool_router, affiliations_router, activity_router, work_domains_router, preview_router, analytics_public_router, analytics_router
from api.routers.scheduler import router as scheduler_router
from api.routers.templates import router as templates_router
from api.routers.runs import router as runs_router
from api.routers.content import router as content_router
from api.routers.publish import router as publish_router
from api.routers.drip import router as drip_router


# ─────────────────────────────────────────────────
# Lifespan events (startup/shutdown)
# ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup/shutdown events

    Startup:
    - Load agents into memory
    - Initialize connections
    - Start background sync for status tracking

    Shutdown:
    - Stop background sync
    - Cleanup resources
    - Close connections
    """
    import asyncio

    # Configure structured logging
    import logging
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Startup
    print("🚀 Starting SEO Robots API...")
    print(f"📍 Project root: {project_root}")
    print("✅ Loading Python agents...")

    # Pre-load agents (optional, for faster first request)
    # Note: Agents will be loaded on-demand when endpoints are called
    print("ℹ️  Agents will be loaded on-demand (lazy loading enabled)")

    # Start background status sync (SQLite → Turso)
    sync_task = None
    try:
        from status.sync import get_sync_service
        sync_svc = get_sync_service()
        if sync_svc.configured:
            sync_task = asyncio.create_task(sync_svc.start_background_sync())
            print("✅ Status sync started (SQLite → Turso)")
        else:
            print("ℹ️  Turso not configured, status sync disabled")
    except Exception as e:
        print(f"⚠ Status sync init failed (non-critical): {e}")

    # Start background scheduler service
    scheduler_task = None
    try:
        from scheduler.scheduler_service import get_scheduler_service
        scheduler_svc = get_scheduler_service()
        scheduler_task = asyncio.create_task(scheduler_svc.start())
        print("✅ Scheduler service started (60s interval)")
    except Exception as e:
        print(f"⚠ Scheduler init failed (non-critical): {e}")

    # Ensure new tables exist (idempotent migrations)
    try:
        from api.services.user_data_store import user_data_store
        if user_data_store.db_client:
            await user_data_store.ensure_affiliate_table()
            await user_data_store.ensure_activity_table()
            await user_data_store.ensure_work_domain_table()
            print("✅ AffiliateLink + ActivityLog + WorkDomain tables ensured")
    except Exception as e:
        print(f"⚠ AffiliateLink migration failed (non-critical): {e}")

    try:
        from api.services.job_store import job_store
        await job_store.ensure_table()
        print("✅ Jobs table ensured")
    except Exception as e:
        print(f"⚠ Jobs table migration failed (non-critical): {e}")

    try:
        from api.services.analytics_store import analytics_store
        if analytics_store.db_client:
            await analytics_store.ensure_pageview_table()
            print("✅ PageView table ensured")
    except Exception as e:
        print(f"⚠ PageView migration failed (non-critical): {e}")

    print("✅ API ready to serve requests")

    yield

    # Shutdown
    if scheduler_task:
        try:
            from scheduler.scheduler_service import get_scheduler_service
            get_scheduler_service().stop()
            scheduler_task.cancel()
            print("✅ Scheduler service stopped")
        except Exception:
            pass
    if sync_task:
        try:
            from status.sync import get_sync_service
            get_sync_service().stop_background_sync()
            sync_task.cancel()
            print("✅ Status sync stopped")
        except Exception:
            pass
    print("👋 Shutting down SEO Robots API...")


# ─────────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────────

app = FastAPI(
    title="SEO Robots API",
    description="""
    🤖 **Multi-Agent SEO Automation System**
    
    Production-grade API exposing Python SEO agents for:
    - **Topical Mesh Analysis** - Audit & improve website structure
    - **Content Strategy** - Generate semantic cocoons
    - **Research & Analysis** - Competitor intelligence
    
    Built with:
    - **FastAPI 0.128.0** (latest stable)
    - **CrewAI** multi-agent orchestration
    - **Pydantic AI** structured validation
    - **NetworkX** graph-based authority calculation
    
    ## Features
    
    - ✅ REST API with auto-validation
    - ✅ WebSocket for real-time streaming
    - ✅ Auto-generated documentation
    - ✅ Type-safe with Pydantic
    - ✅ Dependency injection
    - ✅ Background tasks support
    - ✅ CORS enabled for Next.js
    
    ## Quick Start
    
    ```python
    # Analyze existing website
    POST /api/mesh/analyze
    {
      "repo_url": "https://github.com/user/site"
    }
    
    # Build new mesh
    POST /api/mesh/build
    {
      "main_topic": "Digital Marketing",
      "subtopics": ["SEO", "Social Media"]
    }
    ```
    
    ## WebSocket Real-time
    
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/api/mesh/analyze-stream')
    ws.send(JSON.stringify({ repo_url: "https://github.com/..." }))
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      console.log(`Progress: ${data.percent}%`)
    }
    ```
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "SEO Robots Team",
        "url": "https://github.com/yourusername/contentflow",
    },
    license_info={
        "name": "MIT",
    }
)


# ─────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-process rate limiter. Limits per IP per window."""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.rpm = requests_per_minute
        self._hits: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ("/", "/health", "/version"):
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = 60.0

        hits = self._hits.get(ip, [])
        # Prune old entries
        hits = [t for t in hits if now - t < window]
        if len(hits) >= self.rpm:
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests"},
                headers={"Retry-After": "60"},
            )
        hits.append(now)
        self._hits[ip] = hits

        return await call_next(request)


app.add_middleware(RateLimitMiddleware, requests_per_minute=120)

# CORS - Allow Next.js frontend to call API
# Note: FastAPI CORS middleware doesn't support wildcard subdomains (*.vercel.app)
# Using allow_origin_regex for flexible subdomain matching
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",      # Next.js dev
        "http://localhost:3001",      # Alternative port
        "http://127.0.0.1:3000",      # Alternative localhost
        "https://contentflow.com",    # Legacy production domain
        "https://www.contentflow.com",
        "https://winflowz.com",       # Current production domain
        "https://www.winflowz.com",
        "https://app.winflowz.com",
    ],
    allow_origin_regex=(
        r"https://("
        r"contentflow[a-z0-9-]*\.(vercel\.app|railway\.app|render\.com)"
        r"|[a-z0-9-]+\.winflowz\.com"
        r")$"
    ),
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)


# ─────────────────────────────────────────────────
# Exception Handlers
# ─────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors"""
    import logging
    logging.getLogger("api").exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
        }
    )


# ─────────────────────────────────────────────────
# Include Routers
# ─────────────────────────────────────────────────

# Health & monitoring (no prefix)
app.include_router(health_router)

# Domain routers (with /api prefix)
app.include_router(me_router)
app.include_router(settings_router)
app.include_router(creator_profile_router)
app.include_router(personas_router)
app.include_router(mesh_router)
app.include_router(research_router)
app.include_router(projects_router)
app.include_router(newsletter_router)
app.include_router(deployment_router)
app.include_router(images_router)
app.include_router(status_router)
app.include_router(scheduler_router)
app.include_router(templates_router)
app.include_router(reels_router)
app.include_router(psychology_router)
app.include_router(runs_router)
app.include_router(content_router)
app.include_router(publish_router)
app.include_router(idea_pool_router)
app.include_router(affiliations_router)
app.include_router(activity_router)
app.include_router(work_domains_router)
app.include_router(preview_router)
app.include_router(analytics_public_router)
app.include_router(analytics_router)
app.include_router(drip_router)


# ─────────────────────────────────────────────────
# Run Server
# ─────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))

    print("\n" + "="*60)
    print("🚀 SEO ROBOTS API SERVER")
    print("="*60)
    print(f"\n📚 Documentation:")
    print(f"   Swagger UI: http://localhost:{port}/docs")
    print(f"   ReDoc:      http://localhost:{port}/redoc")
    print(f"\n🔗 Endpoints:")
    print(f"   Health:     http://localhost:{port}/health")
    print(f"   Newsletter: http://localhost:{port}/api/newsletter/config/check")
    print("\n" + "="*60 + "\n")

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,  # Auto-reload on code changes
        log_level="info"
    )
