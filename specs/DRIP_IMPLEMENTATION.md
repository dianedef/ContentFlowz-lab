---
artifact: spec
metadata_schema_version: "1.0"
artifact_version: "1.0.0"
project: contentflow_lab
created: "2026-04-25"
updated: "2026-04-27"
status: reviewed
source_skill: sf-docs
scope: feature
owner: Diane
confidence: high
risk_level: medium
security_impact: unknown
docs_impact: yes
user_story: "Documenter le comportement implémente du module Drip et ses contrats SSG de publication progressive"
linked_systems:
  - "api/routers/drip.py"
  - "api/services/drip_service.py"
  - "scheduler/scheduler_service.py"
  - "tests/test_drip_index_proof.py"
depends_on: []
supersedes: []
evidence:
  - "api/main.py inclut drip_router"
  - "api/routers/drip.py expose les routes /api/drip/*"
  - "api/services/drip_service.py implemente execute_drip_tick et preflight_plan"
  - "tests/test_drip_index_proof.py couvre le mode index-proof"
next_step: "/sf-docs audit specs/DRIP_IMPLEMENTATION.md"
---
# Drip — Progressive Publishing (Implementation Notes)

This document describes the **real implementation** of Content Drip in `contentflow_lab` (FastAPI + scheduler) and the expected **SSG-side contracts** to make it “Google-index-proof”.

## Status rationale

This file is `reviewed` because the implementation it documents is present in the repo:

- `api/main.py` includes `drip_router`
- `api/routers/drip.py` exposes `/api/drip/*` routes
- `api/services/drip_service.py` implements core lifecycle (`activate`, `execute_drip_tick`, `preflight_plan`)
- `scheduler/scheduler_service.py` dispatches `job_type="drip"`
- `tests/test_drip_index_proof.py` asserts index-proof behavior

## What Drip does (server-side)

Drip is a batch orchestrator for SSG content (Astro/Next/Hugo/Jekyll…):

1) Import Markdown files into `content_records` (source_robot=`drip`)
2) Cluster items (directory/tags/auto)
3) Generate a schedule (`scheduled_for` per item)
4) Activate a plan → a scheduler job periodically runs “ticks”
5) On each tick, publish due items:
   - update frontmatter (pubDate/draft/robots depending on config)
   - transition lifecycle statuses (`scheduled → publishing → published`)
   - trigger an SSG rebuild
   - optionally submit URLs to Google (Indexing API)

## Core APIs

- Plans: `POST/GET/PATCH/DELETE /api/drip/plans`
- Import: `POST /api/drip/plans/{id}/import?directory=...`
- Cluster: `POST /api/drip/plans/{id}/cluster?mode=directory|tags|auto`
- Schedule: `POST /api/drip/plans/{id}/schedule`
- Preview schedule: `GET /api/drip/plans/{id}/preview`
- Preflight checks: `GET /api/drip/plans/{id}/preflight`
- Lifecycle: `POST /api/drip/plans/{id}/activate|pause|resume|cancel`
- Manual tick (debug): `POST /api/drip/plans/{id}/execute-tick`

## Index-proof strategy (defense-in-depth)

Drip can only be “index-proof” if **the website build respects these signals**:

### 1) Content gating (frontmatter)

Drip uses `ssg_config.gating_method`:

- `future_date`: writes `pubDate: YYYY-MM-DD` on publish
- `draft_flag`: writes `draft: false` on publish and can set `draft: true` during scheduling
- `both`: does both

### 2) Robots noindex (optional)

If `ssg_config.enforce_robots_noindex_until_publish=true`, Drip writes:

- during scheduling (pre-gate): `robots: "noindex, follow"`
- on publish tick: `robots: "index, follow"`

This is a **second barrier**: even if a page is reachable, it should not be indexed.

### 3) Sitemap exclusion (required)

Your site must exclude pages from sitemap when they are not released.

Recommended rule:

- exclude if `draft: true` OR `robots` starts with `noindex`

### 4) Optional hardening: post-build prune (GoCharbon-like)

If you fully control the site repo, you can add a post-build step that removes non-released pages from `dist/` entirely. This is the most robust approach (nothing to crawl).

## “Safe mode” (mixed sites: new + existing pages)

If you are dripping a folder that might already contain **live pages**, pre-gating (setting `draft: true` / `noindex`) can “depublish” them.

To prevent that, enable safe mode:

- `ssg_config.require_opt_in=true`
- `ssg_config.frontmatter_opt_in_field="dripManaged"` (default)
- Set `dripManaged: true` in frontmatter for files Drip is allowed to mutate.

Preflight will warn for items missing opt-in.

On pause/cancel, the API attempts to restore the original `pubDate/draft/robots` values using a snapshot captured at import time.

## Scheduler behavior

When a plan is activated, the API creates a `schedule_jobs` record with `job_type="drip"` and `configuration.drip_plan_id`.

The background scheduler:

- dispatches `job_type="drip"`
- computes the next run from `drip_plans.next_drip_at` (authoritative)

## Rebuild trigger (SSG)

Configured via `ssg_config.rebuild_method`:

- `webhook`: POST to a deploy hook URL (Vercel/Netlify/Cloudflare Pages)
- `github_actions`: triggers a `workflow_dispatch`
- `manual`: no-op (you rebuild yourself)

## Google Search Console (Indexing API)

Optional. If enabled, Drip can submit the published URLs after each tick.

Server env supported:

- `GSC_SERVICE_ACCOUNT_JSON` (preferred)
- `GSC_SERVICE_ACCOUNT_DATA` (inline JSON)
- Legacy aliases: `GOOGLE_CREDENTIALS_FILE`, `GOOGLE_CREDENTIALS_JSON`

## Troubleshooting

- Pages index too early:
  - ensure the site outputs `<meta name="robots" content="noindex, follow">` for unreleased pages
  - ensure sitemap excludes unreleased pages
  - consider post-build prune hardening
- Tick runs but publishes nothing:
  - check `/api/drip/plans/{id}/preflight` (missing frontmatter / opt-in)
  - verify items have `scheduled_for <= now`
- GSC submission failing:
  - confirm service account is owner in the GSC property
  - confirm Google API libs are installed and credentials env is present
