---
artifact: business_context
metadata_schema_version: "1.0"
artifact_version: "1.0.0"
project: contentflow_lab
created: "2026-04-25"
updated: "2026-04-27"
status: reviewed
source_skill: sf-docs
scope: business
owner: "Diane"
confidence: medium
risk_level: medium
security_impact: unknown
docs_impact: yes
target_audience: "Équipes produit, contenu, marketing et opérations qui utilisent ContentFlow"
value_proposition: "Offrir une couche backend fiable pour synchroniser les workflows de contenu, planification, exécution et observabilité IA."
business_model: "Plateforme logicielle de services pour l’écosystème ContentFlow ; la tarification n’est pas encodée dans ce dépôt."
market: "Teams B2B/B2B2C qui industrialisent production de contenu via API et automatisation."
depends_on: []
supersedes: []
evidence:
  - CLAUDE.md
  - ENVIRONMENT_SETUP.md
  - AGENTS.md
next_review: "2026-07-26"
next_step: /sf-docs audit BUSINESS.md
---
# Business Context

## Positionnement Backend

`contentflow_lab` is the authoritative backend layer for ContentFlow, responsible for:

- data APIs for authenticated product workflows,
- content status/scheduling orchestration,
- AI-assisted analysis and automation endpoints.

For user-facing product truth, `contentflow_app` remains canonical. This repository is authoritative for backend contracts and operational guarantees, not for the primary market promise.

The product promise is operational continuity: the Flutter app stays usable at the user layer while backend flows remain consistent and recoverable.

## User and System Value

- Product teams and operators get a single backend contract for content planning, persona management, drip scheduling, and execution history.
- Marketing and analytics teams get measurable signals (`status`, `analytics`, `jobs`, `cost`) for decisioning and visibility.
- Automation and content teams get orchestrated research/pipeline outputs with traceable execution.

## Commercial Constraint

Pricing and monetization are not encoded in this repository; backend scope is to preserve API reliability and delivery speed for the product stack.

## Service Commitments

- stable API behavior for app-critical flows (`projects`, `settings`, `content`, `drip`),
- secure session-aware access (Clerk-backed validation where configured),
- observability for failed operations and background jobs,
- deployable runtime defaults for EU-hosted/managed environments.

## Current Priorities

- Keep endpoint contracts in sync with app usage.
- Harden migration and startup behavior for fast recovery.
- Preserve backward-compatible payloads where possible during rollout.
