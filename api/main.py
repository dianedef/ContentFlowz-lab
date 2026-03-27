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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.routers import mesh_router, research_router, health_router, projects_router, newsletter_router, deployment_router, images_router, status_router, reels_router, psychology_router, me_router, settings_router, creator_profile_router, personas_router, idea_pool_router
from api.routers.scheduler import router as scheduler_router
from api.routers.templates import router as templates_router
from api.routers.runs import router as runs_router
from api.routers.content import router as content_router
from api.routers.publish import router as publish_router


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
        "url": "https://github.com/yourusername/contentflowz",
    },
    license_info={
        "name": "MIT",
    }
)


# ─────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────

# CORS - Allow Next.js frontend to call API
# Note: FastAPI CORS middleware doesn't support wildcard subdomains (*.vercel.app)
# Using allow_origin_regex for flexible subdomain matching
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",      # Next.js dev
        "http://localhost:3001",      # Alternative port
        "http://127.0.0.1:3000",      # Alternative localhost
        "https://contentflowz.com",       # Production domain
        "https://www.contentflowz.com",   # Production domain
    ],
    allow_origin_regex=r"https://.*\.(vercel\.app|railway\.app|render\.com)$",
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
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc),
            "type": type(exc).__name__
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
