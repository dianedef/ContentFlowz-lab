---
artifact: brand_context
metadata_schema_version: "1.0"
artifact_version: "0.1.0"
project: contentflow_lab
created: "2026-04-25"
updated: "2026-04-26"
status: draft
source_skill: sf-docs
scope: brand
owner: "Diane"
confidence: low
risk_level: medium
security_impact: none
docs_impact: yes
brand_voice: "Précis, fiable, opérationnel et transparent sur les limites"
trust_posture: "Communication claire sur promesses, observabilité des erreurs et sécurité explicite"
depends_on: []
supersedes: []
evidence:
  - BUSINESS.md
  - CLAUDE.md
next_review: "2026-07-26"
next_step: /sf-docs audit BRANDING.md
---
# Branding Guide

## Brand System

- **Product family**: ContentFlow
- **Backend role**: Reliable operations API for AI-assisted content execution.
- **Tone**: Precise, technical, trustworthy.

## Messaging Principles

- Prioritize reliability and recoverability over novelty claims.
- Speak in operational terms: jobs, schedules, workflows, status, contracts.
- Avoid overpromising autonomous generation outcomes.
- Reinforce clarity on validation, auth, and data ownership.

## UX/Product Messaging

- Prefer labels that describe state and intent (e.g. `health`, `queued`, `retry`, `paused`, `active`, `completed`).
- Use deterministic, inspectable terminology for asynchronous jobs and retries.
- Error communication should be explicit and actionable.

## Terms to Favor

- lifecycle
- job execution
- secure handoff
- content workspace
- sync status
- status lifecycle

## Terms to Avoid

- "magic",
- "instant",
- "set and forget",
- "fully automatic".
