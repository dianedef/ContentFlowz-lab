#!/usr/bin/env python3
"""
Entry point for the contentflow API server.
PM2 runs: flox activate -- ./venv/bin/python main.py
The PORT env var (set by PM2) controls the listening port.
"""
import os
import sys

# Load .env if present (for local dev without Doppler)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    reload_enabled = os.environ.get("UVICORN_RELOAD", "").lower() in {"1", "true", "yes"}

    print("\n" + "=" * 60)
    print("🚀 SEO ROBOTS API SERVER")
    print("=" * 60)
    print(f"\n📚 Documentation:")
    print(f"   Swagger UI: http://localhost:{port}/docs")
    print(f"   ReDoc:      http://localhost:{port}/redoc")
    print(f"\n🔗 Endpoints:")
    print(f"   Health:     http://localhost:{port}/health")
    print(f"   Newsletter: http://localhost:{port}/api/newsletter/config/check")
    print("\n" + "=" * 60 + "\n")

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=port,
        reload=reload_enabled,
        log_level="info",
    )
