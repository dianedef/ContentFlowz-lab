# Changelog

All notable changes to Content Flows are documented here.

## [2026-04-08]

### Removed
- **Dead CrewAI objects in Scheduler and Images pipelines** — removed 5 unused `from crewai import` statements, 8 unused `Agent()`/`Task()` factory functions (`create_image_strategist`, `create_strategy_task`, `create_image_generator`, `create_generation_task`, `create_image_optimizer`, `create_optimization_task`, `create_cdn_manager`, `create_deployment_task`), 4 `_create_agent()` methods, and 8 `self.agent = ...` assignments that were created and immediately ignored (-631 lines)

### Changed
- **Renamed `SchedulerCrew` → `SchedulerPipeline`** and **`ImageRobotCrew` → `ImagePipeline`** to reflect their true nature as deterministic Python pipelines, not LLM-orchestrated crews (`scheduler_crew.py`, `image_crew.py`, `agents/images/__init__.py`, `api/dependencies/`, `api/routers/images.py`, example files)
- **`get_image_robot_crew` → `get_image_pipeline`** in FastAPI dependency injection

## [2026-04-07]

### Security
- **Clerk JWT auth on 12 unprotected routers** — deployment, drip, templates, images, mesh, research, scheduler, newsletter, internal_linking, preview, reels, runs now require valid bearer token
- **Shell injection eliminated** — all `subprocess.run(shell=True)` + f-string commands replaced with `shell=False` + list args in publishing_tools.py and tech_audit_tools.py
- **Global exception handler no longer leaks internals** — `str(exc)` removed from 500 responses, errors logged server-side only
- **CORS regex tightened** — `*.vercel.app` narrowed to `contentflowz*.vercel.app`
- **Input sanitization** on test_runner.py user-supplied file paths

### Changed
- **Dependency pins** — all packages in requirements.txt now have upper-bound constraints (e.g. `>=2.0,<3.0`)
- **Structured logging** — `logging.basicConfig` with ISO timestamps and configurable `LOG_LEVEL` env var at startup
- **Rate limiting** — IP-based middleware (120 req/min), returns 429 with `Retry-After` header
- **Health check** — `/health` now tests database connectivity (libsql/Turso) instead of hardcoded "not_configured"

### Fixed
- 7 bare `except:` clauses replaced with `except Exception:` in repo_analyzer.py and seo_research_tools.py
- Drip router now uses authenticated `current_user.user_id` instead of hardcoded `"system"`

## [2026-04-06]

### Added
- **Content Drip module** — publication progressive de contenu SSG, backend complet
  - `api/models/drip.py` — 13 enums + 8 modeles Pydantic (cadence, clustering, SSG, GSC configs)
  - `api/services/drip_service.py` — 17 methodes (CRUD plans, import directory, 3 modes clustering, scheduling fixe/ramp-up, execution tick, plan lifecycle)
  - `api/routers/drip.py` — 17 endpoints `/api/drip/*` (plans CRUD, import, cluster, schedule, preview, activate/pause/resume/cancel, execute-tick, GSC submit/check)
  - `api/services/frontmatter.py` — parser/writer YAML frontmatter pour fichiers Markdown
  - `api/services/rebuild_trigger.py` — trigger rebuild SSG (webhook Vercel/Netlify, GitHub Actions)
  - `api/services/gsc_client.py` — Google Search Console (Indexing API submit + URL Inspection API check)
  - `SourceRobot.DRIP` ajoute aux enums existants
  - Table `drip_plans` dans le schema SQLite
  - Specs : `SPEC-progressive-content-release.md` + `ANALYSIS-drip-integration-with-existing.md`

## [2026-03-30]

### Added
- Social Listener — multi-platform social listening for the Idea Pool
  - `agents/sources/social_listener.py` — collects from Reddit, X, HN, YouTube via Exa AI + HN Algolia API
  - Ranking by engagement velocity (40%), recency (30%), cross-platform convergence (30%)
  - Trigram Jaccard deduplication, question detection (prefixes + "?"), convergence bonus (1.5x for 2+ platforms)
  - `IdeaSource.SOCIAL_LISTENING` added to enum
  - `POST /api/ideas/ingest/social` endpoint for manual trigger
  - `ingest_social` job type in scheduler for automated runs
  - 21 tests (question detection, dedup, convergence, ranking, HN parsing, full flow)
- Content Quality Scoring — fix broken QualityChecker + textstat integration
  - `agents/seo/tools/editing_tools.py` — replaced incomplete Flesch formula with textstat: Flesch Reading Ease, Flesch-Kincaid Grade, Gunning Fog, SMOG, Coleman-Liau, reading time
  - Graceful fallback when textstat is not installed
  - Language support via `textstat.set_lang()`
  - 6 tests (structure, simple/complex scoring, textstat metrics, min words, grade)
- OG Preview service — OpenGraph metadata extraction for link previews
  - `api/services/og_preview.py` — httpx + BeautifulSoup, fallback to `<title>` and `<meta description>`, relative URL resolution, favicon extraction
  - `api/routers/preview.py` — `GET /api/preview?url=...` endpoint
  - Zero new dependencies (httpx + bs4 already in stack)
  - 5 tests (full OG, fallbacks, relative images, empty HTML, model)
- `specs/social-listener.md` — technical specification for social listener module
- Feature documentation on ContentFlowz site:
  - `platform/social-listening.md` — Social Listening feature page
  - `platform/content-quality-scoring.md` — Content Quality Scoring feature page
  - `platform/link-previews.md` — Link Previews feature page
  - Platform index updated with 3 new features

### Changed
- `requirements.txt` — added `textstat>=0.7.0`
- `api/models/idea_pool.py` — added `SOCIAL_LISTENING` to `IdeaSource` enum
- `scheduler/scheduler_service.py` — added `ingest_social` job dispatch + `_run_ingest_social()`
- `api/routers/idea_pool.py` — added `IngestSocialRequest` model + `/ingest/social` endpoint

## [2026-03-29]

### Added
- Cookie-free pageview analytics system — replaces PostHog for project sites
  - `api/services/analytics_store.py` — Turso-backed PageView table with summary, top pages, referrers, and timeseries queries
  - `api/services/ua_parser.py` — lightweight stdlib-only user-agent parser (device, browser, OS)
  - `api/routers/analytics.py` — public endpoints (`GET /a/s.js`, `POST /a/collect`) + authenticated query endpoints (`GET /api/analytics/{summary,pages,referrers,timeseries}?projectId=X`)
  - `api/models/analytics.py` — Pydantic models for collect payload and query responses
  - `agents/seo/tools/inject_analytics.py` — idempotent script injection into project site layouts (Astro, Next.js, Nuxt)
  - Tracking script: ~600 bytes, cookie-free, SPA-aware (pushState + popstate), sendBeacon transport
  - All data EU-hosted, no IP storage, no fingerprinting, GDPR/CCPA compliant without consent banner
  - Query endpoints scoped by `projectId` via WorkDomain relationship for user isolation

### Changed
- Privacy page updated — PostHog references replaced with cookie-free analytics documentation
- Features section — added "Cookie-Free Analytics" card

## [2026-03-10]

### Added
- PostHog injecté dans `website/src/layouts/Layout.astro` (production uniquement, placeholder `POSTHOG_KEY_CONTENTFLOWZ` à remplacer)
- Page `/privacy` créée (`website/src/pages/privacy.astro`) avec bouton opt-out PostHog

## [Unreleased]

### Added
- `website/` blog infrastructure:
  - `BlogPost.astro` layout — reading time (~200 wpm), auto-ToC from headings (≥3 h2/h3), related articles by tag overlap, full prose styles
  - `/blog` index page — featured hero card + responsive post grid
  - `/blog/[...slug]` dynamic route — static generation from content collection
  - `@astrojs/sitemap` — auto-generates `sitemap-index.xml` on every build
  - Layout.astro — OG tags, Twitter card, Article schema.org, canonical URL, Organization schema
- `website/src/content/config.ts` — flexible blog schema: accepts `pubDate`/`publishDate`/`date`, `heroImage`/`image`, `author`/`authors`; `.transform()` normalizes to `date`/`cover`/`byline`
- `GoogleIntegration` — real service account auth for Google APIs (replaces stubs)
  - `trigger_google_indexing`: calls Indexing API v3 with 200/day quota guard, 100ms delay, `quota_remaining` in response
  - `check_indexing_status`: URL Inspection API — returns `coverage_state`, `verdict`, `last_crawled`, `robots_txt_state`
  - `submit_to_google_search_console`: sitemap submission via Search Console API
  - Lazy imports for `google.*` so app doesn't fail without these optional deps
- `google-api-python-client>=2.100.0` + `google-auth>=2.23.0` to requirements.txt
- `GOOGLE_CREDENTIALS_FILE` + `GOOGLE_SITE_URL` env vars to `.env.example` with full setup instructions
- `SitemapMonitor` — health check, coverage check, cross-site batch check
- `check_sitemap_plugin` added to `DependencyAnalyzer` for framework audit
- `LocalLinkChecker` — validates markdown links from source files pre-deploy (no HTTP required)
- Multi-directory content support — `ProjectSettings.content_directories[]` with backward-compat migration
- `RunHistory._RunContext.mark_failed()` — handle early-return failure paths inside context manager
- Chatbot robot runs tab + robots tab — new API routes, React hooks, DB migration
- Strategy frontmatter governance (project-scoped):
  - `POST /api/content/frontmatter-audit` with modes: `audit`, `dry-run`, `autofix`
  - Canonical normalization checks for `funnelStage`, `seoCluster`, `ctaType`, `contentStatus` (+ legacy aliases)
  - Grouped autofix commits (single commit per `repo@branch`) via GitHub tree/commit API
  - JSON/CSV exportable audit report for traceability

### Changed
- `repo_analyzer` — workspace cache-first, clone only on first run, no hardcoded local paths
- GitHub OAuth token now forwarded: Clerk → Next.js proxy → Python API for private repo cloning
- SEO robot run — passes `repo_url` from selected project with improved error messages + copy button on error banner
- API health check now uses importlib instead of file-existence check
- Removed redundant `update_sitemap` from publishing pipeline (Astro owns this via `@astrojs/sitemap`)
- Consolidated RunHistory logging — removed duplicate JSON file logging in `scheduler_crew` + `image_crew`
- `Grow -> Strategy` now treats registered project repositories (`Content Sources`) as the content container source of truth, with strict `projectId` scoping across funnel/cluster analytics
