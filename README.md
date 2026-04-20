# ContentFlow Lab

Backend platform for ContentFlow, centered on FastAPI services and AI automation pipelines for content strategy, scheduling, analytics, and delivery support.

This repository hosts the product API used by:

- `contentflow_app` (Flutter application),
- `contentflow_site` (landing pages + auth handoff flow),
- internal research and operations tooling.

## Architecture

- FastAPI app in `api/` with domain routers (`/api/*` and `/a/*` for public analytics),
- AI/agent layer in `agents/` (CrewAI + PydanticAI),
- scheduler/service layer in `scheduler/`,
- persistence in Turso/SQLite-backed stores (`api/services/*`, `status/*`, `data/*`),
- dashboard/chat integrations where present in the repo (`chatbot/` may be optional per deployment profile).

## Backend Services and Domains

- Project/workspace CRUD and settings (`projects`, `settings`, `creator_profile`, `personas`, `idea_pool`, etc.)
- Content and editorial workflows (`content`, `drip`, `runs`, `templates`, `feedback`)
- SEO and research (`mesh`, `research`, `reels`, `psychology`)
- Statusing and observability (`status`, `analytics`, logs, jobs, cost)
- Auth/session exchange endpoints for Clerk web handoff (`/api/auth/web/*`, `/api/webhooks/clerk`)

## Quick Start

1. Install dependencies: `pip install -r requirements.txt`
2. Configure secrets with Doppler or `.env` fallback:
   - `doppler login`
   - `doppler setup` (`contentflow` project + `dev`)
3. Start API with Doppler:
   - `doppler run -- uvicorn api.main:app --reload --port 8000`
4. Health check:
   - `curl http://localhost:8000/health`
5. Open docs:
   - Swagger: `http://localhost:8000/docs`
   - Redoc: `http://localhost:8000/redoc`

## Deployment and Runtime Notes

- `api/main.py` includes startup/shutdown lifecycle hooks and background scheduler initialization.
- CORS and authentication middleware are configured for Flutter/site/dashboard clients.
- `render.yaml` and `ecosystem.config.cjs` are used for hosted/manual runtime setups.

## Recent API Direction

Primary concern of this repo is service reliability:

- startup resilience (`lifespan` startup checks, idempotent schema creation),
- background job cadence (`scheduler_service`),
- schema and migration safety (`idempotent ensure_*` calls on startup),
- secure handoff paths for web auth sessions used by the app entry flow.

## Project Selection Contract

- The current project for a signed-in user is persisted in `UserSettings.defaultProjectId`.
- `GET /api/me` and `GET /api/bootstrap` resolve the last-opened project from that setting first.
- `Project.isDefault` may still exist in stored rows for backward compatibility, but it is no longer treated as the source of truth for Flutter routing.
- Supported project routes used by the app:
  - `GET /api/projects`
  - `POST /api/projects`
  - `GET /api/projects/{id}`
  - `PATCH /api/projects/{id}`
  - `DELETE /api/projects/{id}`
  - `POST /api/projects/onboard`
  - `POST /api/projects/{id}/analyze`
  - `POST /api/projects/{id}/confirm`

## Project Analysis Data Exposed To Clients

- Project responses include `settings` with detected repo information when available:
  - `tech_stack`
  - `content_directories`
  - `config_overrides`
  - `onboarding_status`
  - `analytics_enabled`
- Flutter can use this to show detected framework, content folders, and configured content/SEO/linking sources without reimplementing repository analysis locally.

## Repository Pointers

- `api/` — API entry and route modules
- `api/routers/` — all FastAPI endpoints
- `api/services/` — domain/service/business logic
- `status/` — lifecycle, cost, and audit primitives
- `agents/` — CrewAI/PydanticAI pipelines
- `scheduler/` — periodic tasks and execution control
- `scripts/` — utilities for environment/setup flows
- `tests/` — validation scripts and unit coverage
