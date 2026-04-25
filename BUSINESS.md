---
artifact: business_context
metadata_schema_version: "1.0"
artifact_version: "0.1.0"
project: contentflow_lab
created: "2026-04-25"
updated: "2026-04-25"
status: draft
source_skill: sf-docs
scope: business
owner: unknown
confidence: low
risk_level: medium
security_impact: unknown
docs_impact: yes
target_audience: unknown
value_proposition: unknown
business_model: unknown
market: unknown
depends_on: []
supersedes: []
evidence: []
next_review: "unknown"
next_step: /sf-docs audit BUSINESS.md
---
# Business Context

## Positionnement Backend

`contentflow_lab` is the authoritative backend layer for ContentFlow, responsible for:

- data APIs for authenticated product workflows,
- content status/scheduling orchestration,
- AI-assisted analysis and automation endpoints.

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
