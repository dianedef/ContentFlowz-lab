---
artifact: technical_context
metadata_schema_version: "1.0"
artifact_version: "0.1.0"
status: draft
project: contentflow_lab
created: "2026-04-26"
updated: "2026-04-26"
source_skill: sf-docs
scope: context
owner: "Diane"
confidence: low
risk_level: high
security_impact: unknown
docs_impact: yes
linked_systems:
  - FastAPI
  - Turso/libsql
  - Clerk
evidence:
  - api/main.py
  - api/routers/__init__.py
  - api/dependencies/__init__.py
  - api/dependencies/auth.py
  - api/services
  - agents
  - memory
  - scheduler
  - status
  - utils
depends_on:
  - AGENT.md
  - GUIDELINES.md
supersedes: []
next_step: /sf-docs audit CONTEXT-FUNCTION-TREE.md
---

# CONTEXT-FUNCTION-TREE.md

## Entry points

- `main.py`
  - process launcher and env bootstrap
  - starts Uvicorn for `api.main:app`

- `api/main.py`
  - app lifecycle (`lifespan`)
  - global middleware and startup/shutdown
  - router mounting and global exception handling

## API layer (`api/`)

- `api/__init__.py`
  - package entry for the API domain

- `api/routers/`
  - domain route modules (health, projects, settings, mesh, research, newsletter, publish, status, jobs, auth, feedback, integrations, etc.)
  - each router owns request/response schemas and endpoint composition

- `api/dependencies/`
  - `auth.py`: Clerk token validation and current user context
  - `ownership.py`: project/content ownership checks
  - `agents.py`: lazy dependency providers for heavy AI classes

- `api/services/`
  - persistence services (user data, credentials, jobs, feedback, analytics)
  - external integrations (OpenRouter/EXA/Firecrawl/Search Console/GSC/Email)
  - runtime orchestration (AI runtime mode and provider validation)

- `api/models/`
  - Pydantic contracts for API I/O and internal schemas

- `api/auth/`
  - Clerk token helper and validation utilities

- `api/migrations/`
  - startup-safe SQL migration files

## Agent layer (`agents/`)

- `agents/seo/`
  - topical mesh, research, copy/content strategist, internal linking flow

- `agents/newsletter/`
  - extraction, memory tools, and newsletter generation

- `agents/reels/`
  - reel processing and upload integrations

- `agents/psychology/`
  - creator and persona psychology modeling agents

- `agents/scheduler/`
  - scheduling coordinator and publishing orchestration helpers

- `agents/shared/` and `agents/sources/`
  - shared prompt/config loading and ingestion sources

## Persistence and orchestration

- `status/`
  - status records, lifecycle transitions, audit trail, and runbook-like history
- `memory/`
  - memory service/config used for semantic continuity
- `utils/`
  - libsql compatibility helpers, helpers, reporting, llm adapters
- `scheduler/`
  - scheduler service loop and dispatch entry points

## Validation and tests

- `tests/`
  - unit, integration, and agent-level test suites
  - fixtures under `tests/fixtures/`
  - execution grouped by function and integration scope

## Deployment and scripts

- `render.yaml`, `ecosystem.config.cjs`, `run_seo_tools.sh`, `main.py`
- command entry for local / production launch and compatibility shim for heavy native dependencies
