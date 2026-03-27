# Changelog

All notable changes to Content Flows are documented here.

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
