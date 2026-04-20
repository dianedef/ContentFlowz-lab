# CLAUDE.md

## Project Overview

`contentflow_lab` is the production-oriented backend platform for the ContentFlow ecosystem.

It hosts:

- a FastAPI runtime used by `contentflow_app`,
- AI automation and research components,
- scheduling, status, and publish-support services used by downstream clients.

## Architecture

- `api/` — FastAPI app and routers:
  - startup/shutdown lifecycle (`api.main`),
  - health + service endpoints,
  - projects/settings/creator/profile/content/drip/jobs/status and analytics APIs.
- `agents/` — CrewAI/PydanticAI pipelines.
- `scheduler/` — periodic orchestration.
- `status/`, `data/`, `utils/` — service and persistence helpers.
- `api/services/` — integrations (analytics, job store, feedback, feedback, drip services, auth/webhand-off helpers).

## Common Commands

```bash
# one-time setup
pip install -r requirements.txt
flox activate  # if using flox

# run API with secrets
doppler run -- uvicorn api.main:app --reload --port 8000
```

```bash
# health + docs
curl http://localhost:8000/health
open http://localhost:8000/docs
open http://localhost:8000/redoc
```

## Backend Focus

- Backend reliability changes must preserve compatibility for authenticated flows consumed by `contentflow_app`.
- Changes to `api/` routers should keep request/response contracts stable and update docs/changelog when impacted.
- New routers should be added with auth, validation, and status/error handling consistent with existing FastAPI patterns.
- Keep startup schema/migration logic defensive (`idempotent`, non-blocking where possible).

## Turso / libSQL Schema Changes (Do Not Skip)

- Production DB is **Turso (SQLite/libSQL)**.
- If you introduce a new table/column/index that the API code relies on, ship the corresponding migration/ensure step in the same change.
- Failure mode is misleading: a missing table (e.g. `UserSettings`) can make onboarding/project selection appear broken and can even trigger upstream 502s.

## Related Projects

- `contentflow_app` — Flutter application and web shell.
- `contentflow_site` — marketing/auth entrypoint.

## References

- `AGENTS.md` for conventions and operational notes.
- `CHANGELOG.md` for endpoint/domain-level changes.
- `ENVIRONMENT_SETUP.md` for secrets and runtime configuration.
