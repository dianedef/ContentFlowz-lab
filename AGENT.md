---
artifact: technical_guidelines
metadata_schema_version: "1.0"
artifact_version: "0.1.0"
status: draft
project: contentflow_lab
created: "2026-04-26"
updated: "2026-04-26"
source_skill: sf-docs
scope: technical
owner: "Diane"
confidence: low
risk_level: high
next_review: "2026-07-26"
security_impact: yes
docs_impact: yes
linked_systems:
  - FastAPI
  - Turso/libsql
  - Clerk
  - OpenRouter
  - Exa
  - Firecrawl
  - SendGrid
  - Doppler
evidence:
  - README.md
  - CLAUDE.md
  - api/main.py
  - api/routers/__init__.py
  - api/dependencies/auth.py
  - api/services/user_data_store.py
  - api/services/user_key_store.py
  - scheduler/scheduler_service.py
  - requirements.txt
  - main.py
depends_on:
  - BUSINESS.md
  - BRANDING.md
  - GUIDELINES.md
supersedes: []
next_step: /sf-docs audit AGENT.md
---

# AGENT.md

## Purpose

This document defines the technical documentation baseline for `contentflow_lab`.
It is the authority for architecture-level notes, runtime boundaries, and documentation governance for the backend codebase.

## Scope and responsibility

- Own the core technical context for:
  - API contracts and auth model
  - persistence strategy and startup initialization
  - scheduler behavior and background processing
  - agent runtime orchestration boundaries
  - dependency and deployment constraints that affect maintainability

- Keep separate from product/marketing artifacts (`PRODUCT.md`, `GTM.md`, `BUSINESS.md`, `BRANDING.md`), except for `depends_on` references.

## Stack baseline inferred from current repo

- Runtime: **Python 3.11**, **FastAPI 0.128+**, **Uvicorn**
- AI/runtime dependencies: **CrewAI**, **PydanticAI**, **OpenAI**, **litellm**, **OpenRouter**, **STORM**, **Spacy/advertools/SERP/DataForSEO**
- Storage/runtime state: **Turso/libSQL** (via `libsql` + compatibility client layer)
- Scheduling: **Async in-process scheduler** started in API lifespan
- Validation/auth: **Clerk JWT/JWKS**, optional **Svix** webhook verification
- Mail/integrations: **SendGrid**, **Gmail/Composio/IMAP** tooling in agent flows

## Runtime contracts and constraints

- Public API and internal tooling are centered in `api/` and served by a single FastAPI application (`api/main.py`).
- Protected routes rely on Clerk bearer token validation (`api/dependencies/auth.py`, `api/auth/clerk.py`).
- Web-to-app handoff (`/api/auth/web`) uses short-lived in-memory handoff tokens (`api/services/web_auth_handoff_store.py`) and consumes to exchange bearer sessions.
- Background jobs execute through `scheduler/scheduler_service.py` at 60-second cadence and can dispatch AI/SEO/newsletter/social workflows.
- DB initialization is startup-driven and idempotent (`ensure_*` patterns in `api/services/*` and `status.service`).

## Documentation operating rules

- Do not document non-existent API/agent modules.
- Do not add claims about production-level guarantees without corresponding code paths.
- Keep docs in sync with:
  - `api/routers/*` registrations (`api/routers/__init__.py`, include list in `api/main.py`)
  - major dependency files (`requirements.txt`, `AGENTS.md`, deployment manifests)
- If dependency or auth behavior changes, update:
  - `CONTEXT.md`
  - `CONTEXT-FUNCTION-TREE.md`
  - `ARCHITECTURE.md`
  - `api/__init__.py` references if route model changes

## Explicit non-goals

- No edits in production deployment copy (`*_deploy` directories) unless explicitly requested.
- No runtime process control commands (`pm2` start/restart/stop/logs) from this context.
