---
artifact: spec
metadata_schema_version: "1.0"
artifact_version: "0.1.0"
project: contentflow_lab
created: "2026-04-25"
updated: "2026-04-25"
status: draft
source_skill: sf-docs
scope: feature
owner: unknown
confidence: low
risk_level: medium
security_impact: unknown
docs_impact: yes
user_story: "unknown (legacy spec migrated to ShipFlow metadata)"
linked_systems: []
depends_on: []
supersedes: []
evidence: []
next_step: "/sf-docs audit specs/SPEC-strict-byok-llm-app-visible-ai.md"
---
# Title
Strict BYOK LLM For App-Visible AI Actions

## Status
Ready for implementation

## Problem
The product decision is now locked: every LLM-backed action visible in `contentflow_app` must run with the requesting user's OpenRouter key, not an operator-managed key from Doppler or process environment.

The current system does not satisfy that requirement:

- `POST /api/personas/draft` already uses `UserProviderCredential` through `contentflow_lab/api/services/user_llm_service.py`, but the rest of the visible AI flows do not.
- `api/routers/psychology.py` launches `ritual`, `angles`, and `dispatch-pipeline` work without resolving a user-scoped LLM at all.
- `api/routers/newsletter.py` and `api/routers/research.py` still depend on server-managed agent construction or config patterns.
- `api/dependencies.py` caches singleton LLM-bound agents, which is incompatible with per-user keys.
- Several app-visible flows already have contract drift between Flutter and FastAPI:
  - `Ritual` sends `entries`, while backend expects `entry_ids`.
  - `Angles` and `Ritual` screens expect final results, while backend returns async task handles.
  - `Newsletter` app paths use `/generate-async` and `/jobs/{job_id}`, while backend exposes `/generate/async` and `/status/{job_id}`.
  - `Research` app payload sends `target_url` and `competitors`, while backend model only requires `keywords`.
- `dispatch-pipeline` fans out into crews that currently create their own status records/content records, which can duplicate outer pipeline ownership.

Without a coordinated migration, removing operator LLM keys from Doppler would either break visible features or silently leave hidden env-based fallbacks in place.

## Solution
Extend the existing OpenRouter user-key foundation into a strict request-scoped runtime used by every current app-visible LLM action. Every such route must resolve the caller's encrypted OpenRouter credential, build explicit OpenRouter clients/`CrewAI` `LLM(...)` objects with that key, and pass them into agents/crews without any fallback to `OPENROUTER_API_KEY`, `GROQ_API_KEY`, or other global LLM env vars.

Keep non-LLM tools server-managed (`Exa`, `Firecrawl`, IMAP/Composio, SendGrid, GitHub OAuth, Turso, encryption secrets). Align the minimal app/backend contracts required so the visible flows still work end-to-end once BYOK is enforced.

## Scope In
- `contentflow_app` visible LLM actions:
  - Persona prefill from repo (`/api/personas/draft`) as regression coverage
  - Ritual narrative synthesis
  - Angle generation
  - Angle-to-content dispatch for `article`, `newsletter`, `short`, `social_post`
  - Newsletter generation and newsletter config readiness
  - Research competitor analysis
- Shared backend BYOK runtime and typed key-resolution errors
- Removal of env-based LLM fallback from the app-visible routes above
- Contract alignment required for the visible flows to function with current Flutter screens
- App UX updates so missing/invalid OpenRouter state is explained consistently and points users to `Settings > OpenRouter`
- Backend automated tests and one targeted Flutter unit-test surface for BYOK error handling

## Scope Out
- `api/templates/generate-prompt` and `api/templates/generate-content`
  - The current Flutter app only calls `GET /api/templates/defaults`
- `api/mesh/build`, `api/mesh/improve`, `api/mesh/compare`, websocket mesh streaming
  - They are not used by the current Flutter screens
- `POST /api/psychology/refine-persona` UI work
  - No current Flutter screen triggers it
  - If touched during backend refactor, it must follow the same BYOK rules, but no new UI is required in this spec
- Removing secrets from Doppler or deleting env vars from deployment config
  - This spec removes runtime dependence for app-visible LLM flows; infra cleanup is a follow-up
- BYOK for non-LLM services: `Exa`, `Firecrawl`, `SendGrid`, `Bunny`, IMAP/Composio, GitHub OAuth
- Changing demo-mode behavior in `contentflow_app`
- Making `/api/mesh/analyze` require OpenRouter
  - The currently exposed mesh analyze path is repo-analysis logic, not an active LLM path

## Constraints
- OpenRouter is the only BYOK LLM provider in V1.
- The encrypted credential in `UserProviderCredential` is the only source of truth for user OpenRouter runtime access.
- App-visible routes may not fall back to `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY`.
- `USER_SECRETS_MASTER_KEY` remains mandatory server infrastructure and is not replaced by BYOK.
- No raw user secret may be stored in:
  - API responses
  - `job_store`
  - status/content metadata
  - logs
- `validation_status == invalid` must block runtime usage.
- `validation_status == unknown` may still be used.
- Async jobs must remain owner-scoped.
- `dispatch-pipeline` must own the single canonical content record for a pipeline run.

## Dependencies
- `contentflow_lab/api/services/user_key_store.py`
- `contentflow_lab/api/services/user_llm_service.py`
- `contentflow_lab/api/services/job_store.py`
- `contentflow_lab/api/routers/settings_integrations.py`
- `CrewAI` request-scoped `LLM(model=..., base_url=..., api_key=...)`
- OpenRouter via OpenAI-compatible endpoint
- Server-managed tools still used inside app-visible workflows:
  - `Exa`
  - `Firecrawl`
  - IMAP/Composio
  - SendGrid
  - GitHub OAuth token forwarding

## Invariants
- Every app-visible LLM request uses the requesting user's OpenRouter credential and no other LLM secret.
- Missing or invalid OpenRouter state returns `409` before any LLM work begins.
- No singleton cache may retain a user-bound LLM client or `CrewAI` agent across requests.
- Background tasks re-resolve user LLM access by `user_id`; they do not serialize raw keys into jobs.
- `dispatch-pipeline` creates exactly one `ContentRecord` per task and downstream crews must not create duplicates.
- Persona draft `mode == blank_form` remains the one visible flow that does not require an OpenRouter key.
- `/api/mesh/analyze` remains callable without OpenRouter because the currently exposed analyze path is not LLM-backed.

## Links & Consequences
- `contentflow_lab/api/services/user_llm_service.py` becomes the single backend entrypoint for building:
  - OpenAI/OpenRouter SDK clients
  - `CrewAI` `LLM` instances
  - standardized runtime errors for missing/invalid credentials
- `contentflow_lab/api/dependencies.py` and `contentflow_lab/api/dependencies/agents.py` cannot keep request-agnostic singleton LLM agents for app-visible research flows. Those caches must be removed or bypassed for BYOK routes.
- `contentflow_lab/api/models/psychology.py` must be aligned to current Flutter payloads, or the BYOK migration will still leave visible screens broken even if LLM resolution is correct.
- `contentflow_app/lib/data/services/api_service.dart` must absorb polling for `ritual` and `angles`, because backend already models them as async jobs and the screens currently expect final data.
- `contentflow_lab/api/routers/newsletter.py` must move off in-memory `_jobs` and onto `job_store` with `user_id`, or BYOK will still leave an owner-scope hole in a visible screen.
- `contentflow_lab/api/routers/research.py` must accept the app's current conceptual inputs (`target_url`, `competitors`, `keywords`) instead of relying on a backend-only keyword contract.
- `contentflow_lab/agents/seo/seo_crew.py`, `agents/newsletter/newsletter_crew.py`, `agents/short/short_crew.py`, and `agents/social/social_crew.py` currently perform nested status/content bookkeeping. Once `dispatch-pipeline` becomes the single outer orchestrator, those nested writes must be disabled in pipeline mode.
- `contentflow_app/lib/presentation/screens/settings/settings_screen.dart` must stop describing OpenRouter as a persona-draft-only requirement.

## Edge Cases
- User has no OpenRouter credential stored.
- User has a stored credential marked `invalid`.
- User stores a key but never validates it (`unknown`).
- User deletes or replaces the key after a job is queued but before the background task starts.
- Newsletter route has a valid user LLM key but missing server-managed dependencies (`Exa`, IMAP/Composio, SendGrid).
- Research screen submits competitors but no keywords.
- `dispatch-pipeline` returns `409` duplicate-content conflict; the app must not fall back to legacy placeholder creation.
- `dispatch-pipeline` is called for `newsletter`, `short`, or `social_post`; nested crews must not create extra content records.
- Demo mode remains mock-backed and must not suddenly require OpenRouter.
- `/api/mesh/analyze` must continue to work for authenticated users with no OpenRouter key.

## Implementation Tasks
- [ ] Task 1: Expand the user-scoped LLM runtime service
  - File: `contentflow_lab/api/services/user_llm_service.py`
  - Action: Introduce typed errors for missing/invalid OpenRouter state and add explicit builders for OpenRouter SDK clients plus `CrewAI` `LLM` instances using request-scoped `api_key` and `base_url`
  - Depends on: none
  - Validate with: backend unit tests that construct runtime objects without reading env fallback
  - Notes: Centralize the model map here; initial defaults are `openai/gpt-4o-mini` for psychology/research/pipeline generation and `anthropic/claude-3.5-sonnet` for newsletter writing

- [ ] Task 2: Normalize the psychology request contracts to match current Flutter usage
  - File: `contentflow_lab/api/models/psychology.py`
  - Action: Replace `NarrativeSynthesisRequest.entry_ids` with `entries` input support, make `AngleGenerationRequest` compatible with current app payloads, and keep legacy aliases only where they do not reintroduce ambiguity
  - Depends on: Task 1
  - Validate with: router tests covering app-shaped payloads for ritual and angles
  - Notes: `refine-persona` may be normalized in the same file even though no current Flutter screen calls it

- [ ] Task 3: Enforce BYOK at psychology route entry and thread runtime into background tasks
  - File: `contentflow_lab/api/routers/psychology.py`
  - Action: Resolve user OpenRouter access before queuing LLM-backed jobs, map missing/invalid credentials to `409`, pass `user_id` through background execution, and keep owner-scoped polling unchanged
  - Depends on: Tasks 1-2
  - Validate with: `tests/test_psychology_auth_jobs.py`
  - Notes: `dispatch-pipeline` must reject before creating a content record when the user key is missing/invalid

- [ ] Task 4: Refactor psychology agents to accept explicit LLM injection
  - File: `contentflow_lab/agents/psychology/creator_psychologist.py`
  - Action: Update the psychology agent constructors/runners to accept an injected `llm` object instead of relying on CrewAI default resolution
  - Depends on: Task 1
  - Validate with: targeted router tests that patch the injected runtime
  - Notes: Apply the same pattern in `agents/psychology/audience_analyst.py` and `agents/psychology/angle_strategist.py`

- [ ] Task 5: Hide psychology async polling behind the Flutter API service
  - File: `contentflow_app/lib/data/services/api_service.dart`
  - Action: Make `synthesizeNarrative()`, `refinePersona()`, and `generateAngles()` submit jobs and poll their status until completion so screens can keep consuming final domain objects
  - Depends on: Tasks 2-3
  - Validate with: manual app smoke on Ritual and Angles plus one unit-tested helper if a shared polling/error helper is introduced
  - Notes: Follow the existing persona-draft polling pattern instead of duplicating ad hoc logic per screen

- [ ] Task 6: Standardize missing-key UX in the app and update OpenRouter copy
  - File: `contentflow_app/lib/presentation/screens/settings/settings_screen.dart`
  - Action: Update helper text and delete-warning copy to describe OpenRouter as the app-wide AI key, not a persona-only key, and add consistent missing/invalid-key handling in the visible AI screens
  - Depends on: Task 5
  - Validate with: manual checks in `Settings`, `Personas`, `Ritual`, `Angles`, `Newsletter`, and `Research`
  - Notes: Reuse a shared helper if introduced; keep the CTA destination as `Settings > OpenRouter`

- [ ] Task 7: Remove implicit env-based LLM resolution from short/social/newsletter/article crews
  - File: `contentflow_lab/agents/short/short_crew.py`
  - Action: Allow explicit `llm` injection and disable internal status/content creation when invoked from `dispatch-pipeline`
  - Depends on: Task 1
  - Validate with: pipeline router tests for `short` generation
  - Notes: Mirror the same changes in `agents/social/social_crew.py`, `agents/newsletter/newsletter_agent.py`, `agents/newsletter/newsletter_crew.py`, `agents/seo/research_analyst.py`, `agents/seo/content_strategist.py`, `agents/seo/copywriter.py`, `agents/seo/on_page_technical_seo.py`, `agents/seo/marketing_strategist.py`, `agents/seo/editor.py`, and `agents/seo/seo_crew.py`

- [ ] Task 8: Repair the article pipeline foundation while moving it to BYOK
  - File: `contentflow_lab/agents/seo/seo_crew.py`
  - Action: Fix the technical SEO import/reference drift, accept injected request-scoped LLM runtime, and ensure inner SEO crew execution does not create a second status/content record when called from `dispatch-pipeline`
  - Depends on: Task 7
  - Validate with: dispatch-pipeline tests for `article`
  - Notes: Use `agents/seo/on_page_technical_seo.py` instead of the missing `technical_seo.py` module

- [ ] Task 9: Migrate newsletter generation to BYOK plus persisted owner-scoped jobs
  - File: `contentflow_lab/api/routers/newsletter.py`
  - Action: Replace in-memory `_jobs` with `job_store`, store `user_id`, resolve the user OpenRouter runtime for generation, and preserve a stable async contract for the app
  - Depends on: Tasks 1 and 7
  - Validate with: new `tests/test_newsletter_router.py`
  - Notes: Add compatibility endpoints or align the contract so both generation and polling paths match the app without silent fallback

- [ ] Task 10: Make newsletter config readiness user-aware without converting non-LLM dependencies to BYOK
  - File: `contentflow_lab/agents/newsletter/config/newsletter_config.py`
  - Action: Stop treating `OPENROUTER_API_KEY` env presence as newsletter LLM readiness for authenticated app usage, and expose separate server-managed vs user-managed readiness signals through `api/routers/newsletter.py`
  - Depends on: Task 9
  - Validate with: newsletter config route tests and manual screen check
  - Notes: Preserve a top-level boolean that the current Flutter screen can still read as `configured`

- [ ] Task 11: Replace cached singleton research agents with request-scoped BYOK construction
  - File: `contentflow_lab/api/routers/research.py`
  - Action: Stop depending on a process-wide cached research agent, resolve the user's OpenRouter runtime per request, and build the agent with explicit `llm`
  - Depends on: Task 1
  - Validate with: new `tests/test_research_router.py`
  - Notes: Update `api/dependencies.py` and `api/dependencies/agents.py` only as needed so no app-visible research path can reuse another user's LLM-bound singleton

- [ ] Task 12: Align the research API contract with the current app screen
  - File: `contentflow_lab/api/models/research.py`
  - Action: Extend the request model to accept `target_url`, `competitors`, and `keywords` from Flutter and normalize them into the agent's actual inputs
  - Depends on: Task 11
  - Validate with: research router tests using the exact app payload shape
  - Notes: Keep the backend deterministic; it should not silently invent a keyword strategy from URLs alone

- [ ] Task 13: Remove unsafe legacy fallback from the Angles screen content-generation path
  - File: `contentflow_app/lib/presentation/screens/angles/angles_screen.dart`
  - Action: Stop falling back to `createContentFromAngle()` for OpenRouter-required or backend-capable pipeline errors; surface the real failure instead
  - Depends on: Tasks 3, 5, and 8
  - Validate with: manual angle-to-content generation checks for `article`, `newsletter`, `short`, and `social_post`
  - Notes: A legacy create-only fallback is acceptable only for explicit demo/mock behavior, not production error masking

- [ ] Task 14: Add regression coverage proving there is no env fallback on app-visible routes
  - File: `contentflow_lab/tests/test_psychology_auth_jobs.py`
  - Action: Extend tests so app-visible routes fail with `409` when the user credential is missing even if dummy global env vars exist in the test process
  - Depends on: Tasks 3, 9, and 11
  - Validate with: pytest
  - Notes: Cover psychology, newsletter, and research; keep existing persona-draft regression in `tests/test_persona_draft_route.py`

- [ ] Task 15: Add a small Flutter test surface for BYOK error detection
  - File: `contentflow_app/test/core/byok_guard_test.dart`
  - Action: Add unit coverage for the shared OpenRouter-required error detection/helper used by visible AI screens
  - Depends on: Task 6
  - Validate with: `flutter test test/core/byok_guard_test.dart`
  - Notes: If no shared helper is introduced, replace this with the smallest realistic unit test covering the chosen error-mapping abstraction

- [ ] Task 16: Make the Research screen explicit about keyword requirements
  - File: `contentflow_app/lib/presentation/screens/research/research_screen.dart`
  - Action: Require at least one keyword before submission, remove the misleading “optional” copy, and keep the same OpenRouter-missing UX used by the other visible AI screens
  - Depends on: Tasks 6 and 12
  - Validate with: manual research-screen submission with and without keywords
  - Notes: This prevents a BYOK-clean backend from still failing behind an ambiguous UI

## Acceptance Criteria
- [ ] CA 1: Given an authenticated user with no stored OpenRouter credential, when they trigger `Ritual`, `Generate Angles`, `Generate Content`, `Newsletter`, or `Research`, then the backend returns `409` before any LLM work starts and the app points them to `Settings > OpenRouter`.
- [ ] CA 2: Given an authenticated user with a credential marked `invalid`, when they trigger the same visible LLM flows, then the backend returns `409` and no job/content record is created.
- [ ] CA 3: Given an authenticated user with a stored credential marked `unknown`, when they trigger a visible LLM flow, then the flow is allowed to run.
- [ ] CA 4: Given a valid user OpenRouter credential, when the user runs `Ritual`, then `contentflow_app` receives a final `NarrativeSynthesisResult` after internal polling and the backend job remains owner-scoped.
- [ ] CA 5: Given a valid user OpenRouter credential, when the user runs `Generate Angles`, then `contentflow_app` receives final angle data after internal polling and no global LLM env var is needed.
- [ ] CA 6: Given a valid user OpenRouter credential, when the user dispatches an angle to `article`, `newsletter`, `short`, or `social_post`, then exactly one canonical `ContentRecord` is created for that dispatch task.
- [ ] CA 7: Given a valid user OpenRouter credential, when the user runs `Newsletter`, then the async job is persisted in `job_store`, scoped to `user_id`, and does not expose raw secrets.
- [ ] CA 8: Given missing server-managed newsletter dependencies but a valid user OpenRouter credential, when the user checks newsletter readiness, then the response distinguishes LLM readiness from server-tool readiness and the screen can still explain what is missing.
- [ ] CA 9: Given the current app payload for `Research` with at least one keyword, when the user runs competitor analysis, then the backend accepts the request shape, uses a request-scoped user LLM, and returns structured results without a cached cross-user agent.
- [ ] CA 10: Given two users with different stored OpenRouter credentials, when they hit visible AI routes on the same backend process, then no request-scoped LLM object or cached agent is reused across those users.
- [ ] CA 11: Given a user without OpenRouter configured, when they run `/api/mesh/analyze` from the current Flutter SEO screen, then the request still works because the exposed mesh-analyze path is not an LLM route.
- [ ] CA 12: Given persona draft `mode == blank_form`, when the user creates the draft job without an OpenRouter credential, then the request still succeeds exactly as it does today.

## Test Strategy
- Backend unit/integration:
  - Extend `tests/test_psychology_auth_jobs.py` for `409` gating, polling ownership, and dispatch pre-check behavior
  - Keep `tests/test_persona_draft_route.py` as regression coverage for persona draft BYOK and blank-form exemption
  - Add `tests/test_newsletter_router.py` for owner-scoped async jobs, config readiness, and no env fallback
  - Add `tests/test_research_router.py` for request normalization and request-scoped LLM injection
  - Add or extend a dispatch/pipeline test to assert a single content record/status owner for nested crews
- Flutter automated:
  - Add one small unit test around the shared OpenRouter-required detection helper used by visible AI screens
- Manual app smoke:
  - `Settings > OpenRouter`: save, validate, delete, updated copy
  - `Personas > Prefill with AI`: success with key, `409` path without key
  - `Ritual`: success with key, settings redirect/error without key
  - `Angles`: generation success with key, settings redirect/error without key
  - `Angles > Generate Content`: one record per dispatch, no fallback placeholder on BYOK errors
  - `Newsletter`: config readiness, job start, owner-scoped polling
  - `Research`: request succeeds with current screen payload and valid key
  - `Research`: missing-key path routes to settings and missing-keyword path is blocked in the UI before network submission
  - `SEO Mesh`: still works without OpenRouter

## Risks
- `CrewAI` request-scoped `LLM(api_key=...)` must actually bypass env fallback in the installed version. If it does not, the migration must pause before shipping.
- `agents/seo/seo_crew.py` already contains a broken technical SEO import path. That must be fixed as part of the migration or article dispatch will remain broken independently of BYOK.
- Research/newsletter/psychology already have app/backend contract drift. Shipping only the key-resolution layer without aligning those contracts would leave the screens broken.
- OpenRouter-compatible model identifiers must be explicit and centralized; legacy direct-provider ids like `groq/...` cannot remain the hidden source of truth for app-visible BYOK paths.
- Background jobs that re-resolve the key at run time can legitimately fail if the user deletes the key after submission. That is acceptable but must surface as a failed job, not a silent hang.

## Execution Notes
- Read first:
  - `contentflow_lab/api/services/user_llm_service.py`
  - `contentflow_lab/api/routers/psychology.py`
  - `contentflow_app/lib/data/services/api_service.dart`
  - `contentflow_lab/agents/newsletter/newsletter_crew.py`
  - `contentflow_lab/agents/seo/seo_crew.py`
- Implementation order:
  1. backend runtime service
  2. psychology contracts and route gating
  3. app polling for psychology
  4. crew injection + dispatch ownership cleanup
  5. newsletter route migration
  6. research route migration
  7. app UX polish and tests
- Validation commands:
  - `cd /home/claude/contentflow/contentflow_lab && pytest tests/test_psychology_auth_jobs.py tests/test_persona_draft_route.py tests/test_settings_integrations_router.py tests/test_newsletter_router.py tests/test_research_router.py`
  - `cd /home/claude/contentflow/contentflow_app && flutter test test/core/byok_guard_test.dart`
- Stop conditions:
  - If explicit request-scoped `CrewAI` LLM injection still triggers env-based auth, stop and re-evaluate the agent integration pattern before touching more routes
  - If pipeline article generation still fails after the import fix, isolate article-pipeline repair as a prerequisite patch before completing the BYOK rollout

## Open Questions
- None. Product decision is fixed: strict BYOK for all current app-visible LLM actions, while non-LLM tools remain server-managed.
