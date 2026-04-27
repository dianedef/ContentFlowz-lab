---
artifact: technical_guidelines
metadata_schema_version: "1.0"
artifact_version: "0.1.0"
status: draft
project: contentflow_lab
created: "2026-04-26"
updated: "2026-04-26"
source_skill: sf-docs
scope: architecture
owner: "Diane"
confidence: low
risk_level: high
security_impact: yes
docs_impact: yes
external_dependencies:
  - SendGrid
  - Gmail IMAP
  - Doppler
  - PM2
  - Render
  - Clerk JWKS endpoint
  - OpenRouter API
  - Exa
  - Firecrawl
  - DataForSEO/SERP APIs
linked_systems:
  - FastAPI
  - Turso/libsql
  - Clerk
  - CrewAI
  - PydanticAI
  - OpenRouter
  - OpenAI-compatible providers
  - Render
evidence:
  - api/main.py
  - api/dependencies/auth.py
  - api/dependencies/agents.py
  - api/routers
  - api/services
  - scheduler/scheduler_service.py
  - status/service.py
  - status/db.py
  - requirements.txt
  - render.yaml
  - ecosystem.config.cjs
  - .env.example
depends_on:
  - CONTEXT.md
  - CONTEXT-FUNCTION-TREE.md
  - BUSINESS.md
  - GUIDELINES.md
supersedes: []
next_review: "2026-07-26"
next_step: /sf-docs audit ARCHITECTURE.md
---

# ARCHITECTURE.md

## High-level architecture

```text
Client surfaces
  ├─ Flutter / web consumers
  └─ Internal tooling
        │
        ▼
  FastAPI app (api/main.py)
        │
        ├─ REST + WebSocket endpoints (api/routers)
        │     ├─ auth + ownership guards
        │     ├─ analytics/research/content/project routes
        │     └─ scheduler + feedback/job routes
        ├─ Dependency providers (api/dependencies)
        │     ├─ Clerk user context
        │     └─ Lazy AI agent loaders
        └─ Service layer (api/services)
              ├─ Turso-backed stores
              │     ├─ user settings/project metadata
              │     ├─ credentials
              │     ├─ jobs/status
              │     └─ feedback
              ├─ agent/runtime services
              │     ├─ AI runtime selector
              │     └─ provider secret handling
              └─ external integrations (OpenRouter/EXA/Firecrawl/etc.)
                    │
                    ▼
               Agent modules (agents/*)
                    │
                    ▼
             Scheduler + status subsystem
                    │
                    ├─ scheduler/scheduler_service.py (60s loop)
                    ├─ status service (content lifecycle + transitions)
                    └─ durable storage in Turso/libSQL
```

## Layer breakdown

- **Presentation boundary (HTTP/WebSocket)**
  - `api/routers/*` expose route contracts and response models.
  - `api/main.py` centralizes middleware and app-wide behavior.

- **Application layer (composition + policy)**
  - `api/dependencies/*` implements auth ownership and provider injection.
  - `api/services/*` contains domain orchestration and external API integration logic.

- **Agent/domain service layer**
  - `agents/*` host the CrewAI/PydanticAI pipelines.
  - Heavy imports are deferred using `lru_cache` providers to protect startup latency.

- **Persistence layer**
  - User/project/security-critical state is persisted to Turso (`libsql`).
  - Status lifecycle uses local adapters with migration-safe schema bootstrapping.

- **Background processing**
  - In-process scheduler (`scheduler/scheduler_service.py`) executes periodic jobs and updates state transitions.
  - Jobs can invoke newsletter/SEO/social pipeline steps.

## External dependencies and boundaries

- **Clerk**
  - JWT auth validation for protected routes.
  - Webhook verification for user events (`api/routers/auth_web.py`).

- **AI/Research providers**
  - OpenRouter (primary LLM path) and provider-specific integrations managed by runtime mode + credential model.
  - Search/ crawler integrations (EXA, Firecrawl, dataforSEO, SERP, etc.) used by agent tools.

- **Email and productivity integrations**
  - SendGrid for outbound mail.
  - IMAP / Gmail-based newsletter intake paths in newsletter tools.

## Constraints and invariants

- Keep startup non-breaking:
  - scheduler startup and DB ensure calls must degrade gracefully on partial failure.
- Keep migrations additive:
  - add tables/columns with idempotent checks and startup safety.
- Keep auth consistent:
  - never bypass `require_current_user` for routes that expose user-owned data.
- Preserve request accountability:
  - ownership checks must remain for cross-project/resource access.
