---
artifact: technical_guidelines
metadata_schema_version: "1.0"
artifact_version: "1.0.0"
project: contentflow_lab
created: "2026-04-25"
updated: "2026-04-27"
status: reviewed
source_skill: sf-docs
scope: guidelines
owner: "Diane"
confidence: medium
risk_level: medium
security_impact: none
docs_impact: yes
linked_systems: []
depends_on: []
supersedes: []
evidence:
  - CLAUDE.md
  - BUSINESS.md
  - BRANDING.md
next_review: "2026-07-26"
next_step: /sf-docs audit GUIDELINES.md
---
# Development Guidelines

## Scope

Backend/API conventions for `contentflow_lab`.

## Stack

- Python 3.11+
- FastAPI
- Pydantic / PydanticAI / CrewAI
- Scheduler + job orchestration
- SQLite/Turso persistence layer
- Doppler for secrets, Flox for reproducible env

## API Rules

1. Keep domain boundaries clear in `api/routers`.
2. Use Pydantic models for public request/response boundaries.
3. Protect sensitive endpoints with auth dependencies.
4. Keep startup initialization idempotent and explicit in logs.
5. Document or update endpoint effects in `CHANGELOG.md` when contract changes.

## Data and Migration Rules

- Avoid destructive DB changes in hot code paths.
- Add new tables/columns via migration-safe paths with clear fallback behavior.
- Ensure background services handle transient failures without taking down the app.
- Keep scheduler jobs deterministic and easy to retry.

## Observability Rules

- Return consistent status semantics (`ok`, `error`, `details`, `request_id` where applicable).
- Keep failures observable (logs + status endpoints + structured events).
- Ensure cost/status tracking surfaces exist for long-running AI jobs.

## Release Hygiene

- When adding new endpoints:
  - update `api/` router registration,
  - update env/deployment docs (`ENVIRONMENT_SETUP.md`, `README.md`),
  - include migration impact in `CHANGELOG.md`.
- If contract changes affect `contentflow_app`, flag compatibility considerations immediately in notes.
