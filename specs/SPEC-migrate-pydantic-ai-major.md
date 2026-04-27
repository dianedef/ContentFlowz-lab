---
artifact: spec
metadata_schema_version: "1.0"
artifact_version: "1.0.0"
project: contentflow_lab
created: "2026-04-27"
updated: "2026-04-27"
status: ready
source_skill: sf-spec
scope: migration
owner: "Diane"
user_story: "En tant que mainteneuse du backend ContentFlow, je veux introduire PydanticAI via un adapter unique sur des flux JSON structurés, afin que les sorties IA soient typées, testables et compatibles avec les credentials BYOK/platform existants."
risk_level: medium
security_impact: yes
docs_impact: yes
linked_systems:
  - FastAPI backend
  - CrewAI SEO agents
  - AI runtime BYOK/platform resolver
  - OpenRouter
  - Exa
  - Firecrawl
  - pytest
  - contentflow_app
  - Turso/libSQL
  - dependency management
  - external URL fetching surface
  - SSRF controls
depends_on:
  - artifact: "CLAUDE.md"
    artifact_version: "0.1.0"
    required_status: "active"
  - artifact: "AGENTS.md"
    artifact_version: "unknown"
    required_status: "active"
  - artifact: "requirements.txt"
    artifact_version: "unknown"
    required_status: "active"
  - artifact: "requirements-dev.txt"
    artifact_version: "unknown"
    required_status: "active"
  - artifact: "Pydantic AI Upgrade Guide"
    artifact_version: "docs current on 2026-04-27"
    required_status: "reviewed"
  - artifact: "Pydantic AI Version Policy"
    artifact_version: "docs current on 2026-04-27"
    required_status: "reviewed"
  - artifact: "Pydantic AI OpenRouter Docs"
    artifact_version: "docs current on 2026-04-27"
    required_status: "reviewed"
supersedes: []
evidence:
  - "CLAUDE.md: backend reliability and deployment-copy boundaries"
  - "requirements.txt: pydantic-ai>=0.1.0,<1.0 and pydantic>=2.4.0,<3.0"
  - "requirements-dev.txt: test dependency file includes -r requirements.txt"
  - "rg: no direct pydantic_ai imports found in agents/, api/, tests/"
  - "python3 importlib.metadata: pydantic-ai not installed locally, pydantic==2.12.5, fastapi==0.116.1, crewai not installed locally"
  - "agents/seo/research_analyst.py: CrewAI Agent with Exa and Firecrawl tools"
  - "api/routers/research.py: request-scoped AI runtime and user_llm_service.get_crewai_llm"
  - "agents/shared/tools/firecrawl_tools.py and agents/shared/tools/exa_tools.py: URL-fetching tools exposed to LLM-guided agents"
  - "Pydantic AI Upgrade Guide: V1 reached API stability in September 2025; V1 breaking changes include Python 3.9 drop, result_type->output_type, result.data->result.output, tool definition ordering, retry config changes"
  - "Pydantic AI Version Policy: V2 no earlier than April 2026; V1 security fixes continue at least 6 months after V2"
  - "Pydantic AI OpenRouter docs: OpenRouterModel can use explicit OpenRouterProvider(api_key=...) or OPENROUTER_API_KEY env"
  - "Exploration 2026-04-27: PydanticAI is not currently imported at runtime, but has concrete value for repo understanding, psychology agents, and typed BYOK flows"
next_step: "Implement PydanticAI adapter spike on repo understanding or psychology JSON flow"
---
# Title
Introduce PydanticAI Through A Single Runtime Adapter

# Status
Ready. The product/technical direction is confirmed: do not remove `pydantic-ai` as a default action. Introduce it deliberately through one adapter and one or two high-value structured-output flows.

# Questions ouvertes (non bloquantes)
- Version cible exacte a verifier au moment de l'implementation avec les docs et metadonnees package officielles.
- Premier flux pilote a choisir entre `repo_understanding_service.py` et les agents psychology.
- Strategie de rollout: feature flag temporaire ou chemin interne non expose jusqu'aux tests.

# User Story
En tant que mainteneuse du backend ContentFlow, je veux introduire `pydantic-ai` via un adapter unique sur des flux IA structurés, afin que les réponses JSON fragiles deviennent typées, testables, et compatibles avec les règles BYOK/platform existantes.

Acteur principal: mainteneuse backend / agent d'implémentation.

Déclencheur: `pydantic-ai` est déclaré dans `requirements.txt` et mentionné dans les docs, mais l'exploration montre qu'il n'est pas encore utilisé au runtime alors qu'il serait utile pour les sorties structurées.

Résultat observable: un adapter PydanticAI unique existe, la contrainte package cible une major supportée, un premier flux structuré l'utilise, les tests ciblés passent, aucun flux app-visible ne contourne les credentials request-scoped, et les outils URL ne deviennent pas plus permissifs.

Assumptions:

- The current repo scan is authoritative for this spec: there are no direct `pydantic_ai` imports in `agents/`, `api/`, or `tests/` at spec time.
- Existing `Agent(...)` constructors in `agents/` are CrewAI agents, not PydanticAI agents.
- `pydantic-ai` is currently a declared dependency and product/architecture intention, not an active runtime implementation.
- PydanticAI should be introduced incrementally where it fits better than CrewAI: typed JSON output, typed dependencies, and request-scoped provider handling.
- All PydanticAI usage must route through the existing ContentFlow AI runtime resolver, not through global provider environment variables.

# Minimal Behavior Contract
The implementation must keep `pydantic-ai` as an intentional dependency, update it to a supported major line, and introduce a single compatibility/runtime adapter. Existing FastAPI endpoints and CrewAI agent flows must keep their request/response contracts, BYOK/platform credential semantics, lazy imports, and failure envelopes. PydanticAI must use explicit request-scoped provider credentials and typed dependencies, never ambient `OPENROUTER_API_KEY` fallback for app-visible actions. On install, import, model-construction, credential, provider, validation, or external-tool failure, the system must fail closed with the existing structured runtime errors or route-specific 4xx/5xx behavior, not leak secrets and not broaden SSRF-capable URL access. The easy-to-miss edge case is that LLM-guided tools such as Firecrawl/Exa can fetch arbitrary URLs; introducing PydanticAI must not bypass or weaken URL validation, provider scoping, or optional-provider gating.

# Success Behavior
- `requirements.txt` no longer exposes the stale `<1.0` PydanticAI risk unintentionally.
- `pydantic-ai` targets the current supported major line with a bounded version range chosen from official docs/package metadata at implementation time.
- All direct PydanticAI usage goes through one compatibility wrapper rather than scattered `pydantic_ai` imports through routers.
- At least one high-value structured-output flow uses the adapter, preferably `repo_understanding_service.py` or one psychology JSON flow.
- Existing routes, especially `POST /api/research/competitor-analysis`, continue to resolve `openrouter`, `exa`, and optional `firecrawl` through `ai_runtime_service.preflight_providers`.
- User-managed OpenRouter keys remain request-scoped through `user_llm_service` and `UserProviderCredential`; platform mode remains entitlement-gated.
- Direct PydanticAI model/provider initialization is centralized in the adapter and uses explicit `OpenRouterProvider(api_key=...)` or equivalent request-scoped provider construction, never ambient provider env for app-visible actions.
- Tests cover dependency policy, import behavior, runtime error mapping, and URL/tool safety boundaries.
- Rollback is available by reverting only dependency/spec/test commits or restoring the previous dependency constraint without DB migration.

# Error Behavior
- Missing user OpenRouter credentials still produce the existing `409` AI runtime error envelope on app-visible BYOK routes.
- Missing operator provider credentials in platform mode still produce the existing `503` operator-provider unavailable/missing shape.
- Invalid user credentials still fail before agent execution and do not instantiate agent toolchains with partial secrets.
- Missing optional Firecrawl credentials keep Firecrawl tools excluded where the route already gates them as optional.
- PydanticAI import or constructor failures, if the package is retained, are isolated to a compatibility module and translated to deterministic runtime errors.
- External URL fetch attempts that are malformed, unsupported scheme, private network, loopback, link-local, metadata IP, localhost, or non-HTTP(S) must be rejected before reaching Exa, Firecrawl, requests, or future PydanticAI tools.
- No exception response may include provider API keys, decrypted credentials, environment variable values, raw auth headers, or full prompt payloads containing secrets.

# Problem
`requirements.txt` currently declares `pydantic-ai>=0.1.0,<1.0`, which leaves ContentFlow below the V1 API-stability line documented by PydanticAI and keeps a dependency audit risk open. Official PydanticAI docs show V1 reached stability in September 2025, while pre-V1 minor releases included breaking changes such as `result_type` removal in favor of `output_type`, `AgentRunResult.data` removal in favor of `output`, tool definition argument ordering changes, stream/model request changes, and retry config changes.

The repository scan complicates this: current backend agent code does not directly import `pydantic_ai`. The active agent implementation uses CrewAI (`from crewai import Agent, Task, Crew`) and request-scoped `CrewAI LLM` creation through `user_llm_service.get_crewai_llm`.

The exploration result changes the decision: this is not a removal task. PydanticAI is not active today, but it is useful for ContentFlow's fragile structured-output paths:

- `api/services/repo_understanding_service.py` currently depends on JSON generation and manual parsing.
- `agents/psychology/*` agents use CrewAI and then parse raw JSON with fallbacks.
- `api/routers/research.py` performs heuristic markdown-to-response parsing.
- The BYOK/platform runtime already has request-scoped provider services that can feed PydanticAI dependencies safely.

The real risk is therefore twofold:

- Dependency hygiene risk: a declared dependency remains stuck on a stale pre-stability range.
- Runtime/security regression risk: introducing PydanticAI without an adapter could accidentally use ambient environment credentials, global singleton agents, or model tools that broaden SSRF-capable URL surfaces.

# Solution
Use an incremental introduction with a dependency inventory gate first.

Preferred path: keep `pydantic-ai`, update it to the supported major line selected from official docs/package metadata, and introduce `api/services/pydantic_ai_runtime.py` as the only approved adapter. The adapter must map ContentFlow runtime resolution to PydanticAI's current API: `Agent(..., output_type=...)`, `result.output`, typed `deps_type`, `RunContext`, explicit `OpenRouterModel`/`OpenRouterProvider(api_key=...)`, and current tool decorators. No router should instantiate PydanticAI provider clients directly.

Pilot path: migrate one low-risk structured-output flow first. Preferred pilots are `repo_understanding_service.py` or one psychology JSON flow. Do not rewrite SEO CrewAI orchestration wholesale; `agents/seo/seo_crew.py` already uses CrewAI `output_pydantic`, so it is not the first target.

Security solution: add or enforce a shared URL safety gate before any LLM-controllable tool can fetch URLs. This gate should be independent of PydanticAI and reused by Firecrawl/Exa wrappers and any future PydanticAI tools.

Rollback solution: because no DB schema change is needed, rollback is dependency-only. Revert the dependency/spec/test commit or restore the prior constraint if production install unexpectedly depends on `pydantic-ai`. Feature flags are not required unless new PydanticAI runtime code is introduced; if introduced, it must be disabled by default behind a route-local or service-level switch until verified.

# Scope In
- Inventory and codify whether `pydantic-ai` is used directly in `agents/`, `api/`, or `tests/`.
- Update `requirements.txt` dependency policy for `pydantic-ai` by pinning it to a supported current major.
- Preserve `requirements-dev.txt` inclusion of runtime dependencies through `-r requirements.txt`.
- Add tests or a lightweight policy check that detects accidental direct `pydantic_ai` usage outside the approved adapter.
- Introduce one compatibility adapter for PydanticAI model/provider construction and result access.
- Migrate one pilot structured-output flow through the adapter.
- Preserve FastAPI route contracts for research, mesh, internal linking, psychology, newsletter, and persona flows touched by agent/runtime dependencies.
- Preserve request-scoped BYOK/platform credential resolution and `ai_runtime_service` error envelopes.
- Add or specify SSRF/URL guard tests for Exa/Firecrawl/future PydanticAI tool entrypoints.
- Update docs/changelog notes that PydanticAI was retained intentionally, upgraded to a supported range, and introduced through the adapter.
- Verify no Turso/libSQL migration is required.

# Scope Out
- Rewriting CrewAI agents to PydanticAI wholesale.
- Removing `pydantic-ai` as the default answer to current non-usage.
- Changing public API request/response models for `contentflow_app`.
- Changing provider mode semantics, entitlement policy, user key encryption, or Turso schemas.
- Removing CrewAI, LiteLLM, OpenAI SDK, Exa, Firecrawl, or provider integrations unrelated to the dependency risk.
- Adding new AI features, new routes, new UI, or new provider support.
- Touching `/home/claude/contentflow/contentflow_lab_deploy`, PM2, or live services.
- Applying production migrations or deployment commands.
- Solving unrelated dependency changes already present in the workspace.

# Constraints
- Work only in `/home/claude/contentflow/contentflow_lab` and the requested spec file.
- Do not revert or overwrite parallel-agent changes; current observed dirty files include `requirements.txt` and untracked `requirements-dev.txt`.
- No destructive git commands.
- Keep backend reliability compatible with authenticated flows consumed by `contentflow_app`.
- Keep lazy imports for heavy agent dependencies so FastAPI health/startup remains fast.
- Do not introduce DB schema changes unless implementation discovers a concrete need; expected Turso migration requirement is `no`.
- Keep Pydantic v2 compatibility: current environment reports `pydantic==2.12.5`.
- Current local environment does not have `pydantic-ai` or `crewai` installed, so implementation must verify in the project runtime environment or dependency install environment before claiming full runtime success.
- Use official PydanticAI docs current at implementation time before finalizing exact target version because PydanticAI V2 may have released on or after April 2026.
- For app-visible AI flows, do not use ambient `OPENROUTER_API_KEY` fallback. Explicit provider credentials from `ai_runtime_service` remain mandatory.
- URL safety must be fail-closed, and DNS rebinding/private-IP checks must not rely solely on string matching.

# Dependencies
Internal dependencies:

- `requirements.txt`: currently declares `pydantic-ai>=0.1.0,<1.0`, `pydantic>=2.4.0,<3.0`, `crewai>=0.1.0,<1.0`, OpenAI SDK, LiteLLM, Exa, Firecrawl, FastAPI.
- `requirements-dev.txt`: includes `-r requirements.txt`, `pytest`, `pytest-asyncio`, `pytest-cov`.
- `api/services/ai_runtime_service.py`: central provider and mode resolver for `openrouter`, `exa`, `firecrawl`.
- `api/services/user_llm_service.py`: request-scoped OpenRouter clients and CrewAI LLM construction.
- `api/routers/research.py`: representative app-visible AI route with BYOK/platform provider preflight and optional Firecrawl gating.
- `agents/seo/research_analyst.py`: CrewAI agent using Exa and Firecrawl tools.
- `agents/shared/tools/exa_tools.py`: external URL/search/content tool surface using runtime provider context.
- `agents/shared/tools/firecrawl_tools.py`: external scrape/crawl/map/search URL tool surface using runtime provider context.
- `tests/test_research_router.py`: current route-level tests for user-key enforcement and normalized payloads.
- `tests/agents/test_research_analyst.py` and `tests/fixtures/agent_fixtures.py`: agent import/fixture surfaces, though fixtures appear stale because they patch `get_balanced_llm` which is not present in scanned agent files.

External dependencies and fresh-docs verdict:

- PydanticAI Upgrade Guide, checked 2026-04-27, verdict `fresh-docs checked`: V1 reached API stability in September 2025; pre-V1 changes renamed `result`/`data` concepts to `output`, removed `result_type` in favor of `output_type`, changed tool definition ordering, and changed retry config requirements.
- PydanticAI Version Policy, checked 2026-04-27, verdict `fresh-docs checked`: V1 avoids intentional breaking minor releases; V2 no earlier than April 2026 and V1 receives security fixes for at least six months after V2.
- PydanticAI OpenRouter docs, checked 2026-04-27, verdict `fresh-docs checked`: OpenRouter can be used by name with `OPENROUTER_API_KEY` or explicit `OpenRouterProvider(api_key=...)`; ContentFlow must choose explicit provider construction for app-visible BYOK/platform flows.
- PydanticAI Dependencies and Tools docs, checked 2026-04-27, verdict `fresh-docs checked`: dependencies use `RunContext`/`deps_type`; tools can be registered through decorators or `tools=`.

# Invariants
- App-visible AI routes must resolve runtime mode and provider credentials before agent execution.
- BYOK credentials are user-scoped and encrypted at rest through existing user-key storage; implementation must not introduce a parallel secret store.
- Platform mode remains entitlement-gated and reads operator secrets only through approved runtime resolution.
- The API must not leak secrets in logs, exceptions, prompts, traces, or response bodies.
- Existing FastAPI request/response schemas remain stable unless a separate spec authorizes contract changes.
- Lazy imports remain in routers/dependencies for heavy agent packages.
- Existing `ai_runtime_service.bind_provider_env(resolution)` semantics remain intact for Exa/Firecrawl tool wrappers.
- Agent construction must not rely on global singleton instances that capture one user's credentials and reuse them for another user.
- External URL tools must accept only normalized, policy-approved HTTP(S) public URLs.
- No Turso migration is expected; if implementation changes persisted data, stop and create a separate migration spec or update this spec before coding.

# Links & Consequences
Upstream:

- Dependency audit/backlog risk is the trigger.
- PydanticAI package/version policy controls whether removal or migration is the right dependency response.
- Existing `requirements.txt` and deployment install process determine production package set.

Downstream:

- `contentflow_app` depends on stable error semantics and AI route contracts.
- FastAPI startup/health check depends on lazy imports and avoiding heavy ML dependency import at module load.
- Research, newsletter, psychology, persona, mesh, and internal-linking flows depend on current provider resolution and agent patterns.
- Exa/Firecrawl tools are LLM-callable and therefore security-sensitive.
- CI/deploy dependency install can change if `pydantic-ai` removal reveals a hidden runtime dependency.

Operational consequences:

- No DB migration expected.
- No auth model changes expected.
- No SEO/analytics/a11y consequences expected.
- Performance should remain stable; the adapter must stay lazy and avoid import-time provider initialization.
- Build/install reproducibility improves when the stale pre-V1 constraint is replaced with an intentional supported range.

Security consequences:

- Positive if introduced through adapter: explicit credential handling, isolated API compatibility, and testable structured output.
- Negative risk if migration introduces ambient env fallback, permissive tool URLs, or global agents with captured credentials.

# Documentation Coherence
Update or verify:

- `CHANGELOG.md`: add a concise dependency/security-risk entry after implementation.
- `requirements.txt` comments: document `pydantic-ai` as an intentional supported dependency if the project keeps dependency comments.
- `AGENTS.md` or `CLAUDE.md`: only update if implementation adds a new PydanticAI adapter or policy for future agents.
- `tests/README.md`: optional, only if a new dependency-policy test category is added.
- Existing specs that mention PydanticAI only as stack context may remain unchanged unless they become inaccurate.

No update required:

- API docs/OpenAPI, if request/response contracts remain unchanged.
- Business, branding, content guidelines, SEO docs.
- Turso migration docs, unless implementation unexpectedly changes data persistence.

Metadata debt:

- `requirements.txt` and `requirements-dev.txt` have no artifact metadata version.
- `AGENTS.md` has no frontmatter/version metadata.

# Edge Cases
- `pydantic-ai` is declared but not yet used directly: a fresh scan is still required so the adapter does not collide with hidden/import-time usage.
- `Agent` name collision: CrewAI and PydanticAI both expose `Agent`; imports must be explicit and not confused in tests or adapters.
- Current local environment lacks `pydantic-ai` and `crewai`: test results from this environment may validate static policy but not full agent runtime unless dependencies are installed.
- PydanticAI V2 may be available as of April 2026: implementation must verify official docs/version before choosing `<2` or `<3` target. Prefer the supported stable major appropriate for a new adapter, not the stale `<1.0` range.
- PydanticAI API migrations: `result_type`, `result_retries`, `result_validator`, `last_run_messages`, and `.data` usage must not be introduced; use `output_type`, `output_retries`, output validators, and `.output`.
- Tool functions that perform IO may run in async contexts/thread pools; URL and credential validation must happen before tool execution, not inside LLM prompts.
- OpenRouter docs allow env-based provider selection; ContentFlow app-visible flows must instead use explicit provider construction or existing request-scoped CrewAI LLMs.
- Optional Firecrawl: when unavailable, `ResearchAnalystAgent` must not include scrape/crawl tools for a route whose preflight did not resolve Firecrawl.
- SSRF surface: model-suggested URLs, competitor URLs, target URLs, Firecrawl crawl roots, Exa similar-page URLs, redirects, DNS rebinding, IPv6, numeric IPv4, punycode/IDN, and localhost aliases must be treated as untrusted.
- Error text from external providers can contain URLs or payload fragments; sanitize before returning to clients.
- Parallel-agent changes in dependency files must be preserved and merged manually, not overwritten.

# Implementation Tasks
- [ ] Tâche 1 : Reconfirm dependency and usage inventory
  - Fichier : `requirements.txt`, `requirements-dev.txt`, `agents/`, `api/`, `tests/`
  - Action : Run a fresh full-repo search for `pydantic_ai`, `pydantic-ai`, `from pydantic_ai`, `result_type`, `result_retries`, `.data`, `AgentRunResult`, `RunContext`, `OpenRouterModel`, and direct provider/env patterns before editing dependencies.
  - User story link : Establishes the current baseline before introducing the adapter.
  - Depends on : None
  - Validate with : `rg -n "pydantic_ai|pydantic-ai|from pydantic_ai|result_type|result_retries|AgentRunResult|OpenRouterModel|RunContext" .`
  - Notes : Do not overwrite existing dirty changes in `requirements.txt` or `requirements-dev.txt`; inspect diffs first.

- [ ] Tâche 2 : Update `requirements.txt` to a supported PydanticAI major
  - Fichier : `requirements.txt`
  - Action : Replace `pydantic-ai>=0.1.0,<1.0` with a supported current major range chosen from official docs/package metadata and record why.
  - User story link : Keeps the dependency intentional and compatible before adding runtime usage.
  - Depends on : Tâche 1
  - Validate with : `git diff -- requirements.txt` and dependency install/resolve command used by the project environment.
  - Notes : Do not remove `pydantic-ai`; this spec intentionally introduces it through one adapter.

- [ ] Tâche 3 : Add dependency-policy regression test
  - Fichier : `tests/test_dependency_policy.py`
  - Action : Add a test that scans repo Python files and fails if `pydantic_ai` is imported outside an approved adapter path. Assert the approved range is not `<1.0` and the adapter path exists once migration starts.
  - User story link : Prevents the risk from reappearing silently.
  - Depends on : Tâche 2
  - Validate with : `pytest tests/test_dependency_policy.py`
  - Notes : Keep the test lightweight and independent of installing `pydantic-ai`.

- [ ] Tâche 4 : Introduce PydanticAI adapter
  - Fichier : `api/services/pydantic_ai_runtime.py`
  - Action : Create a narrow adapter that accepts an already-resolved ContentFlow runtime secret and returns current PydanticAI model/agent primitives using explicit provider construction. Expose helper methods for result `.output` access and typed dependency injection.
  - User story link : Keeps compatibility and credential behavior centralized if migration is necessary.
  - Depends on : Tâche 2
  - Validate with : Unit tests using PydanticAI test/function model or monkeypatched adapter imports.
  - Notes : Keep the adapter small; it should not replace CrewAI orchestration globally.

- [ ] Tâche 5 : Add adapter compatibility tests
  - Fichier : `tests/test_pydantic_ai_runtime.py`
  - Action : Test explicit OpenRouter provider construction path, no ambient env fallback, result output access, runtime error translation, and dependency injection assumptions.
  - User story link : Verifies the supported-major API is used correctly.
  - Depends on : Tâche 4
  - Validate with : `pytest tests/test_pydantic_ai_runtime.py`
  - Notes : Prefer monkeypatching over live provider calls; no network calls in unit tests.

- [ ] Tâche 6 : Add shared URL safety gate for LLM-callable external tools
  - Fichier : `api/services/url_safety.py`
  - Action : Implement URL normalization and public-network validation for HTTP(S) URLs: reject empty values, unsupported schemes, credentials in URL, localhost, loopback, private, link-local, multicast, reserved, metadata IPs, and suspicious redirects if redirect resolution is added.
  - User story link : Ensures migration does not broaden SSRF exposure.
  - Depends on : Tâche 1
  - Validate with : `pytest tests/test_url_safety.py`
  - Notes : Use `urllib.parse`, `ipaddress`, and DNS resolution carefully. If DNS resolution is not appropriate in unit tests, split pure parsing from resolver-injected checks.

- [ ] Tâche 7 : Apply URL safety to Firecrawl tools
  - Fichier : `agents/shared/tools/firecrawl_tools.py`
  - Action : Call the shared URL safety gate before `scrape_url`, `crawl_site`, and `map_site` reach `FirecrawlApp`; return a safe error string without calling the provider when rejected.
  - User story link : Protects LLM-guided crawl/scrape surfaces.
  - Depends on : Tâche 6
  - Validate with : Unit tests that monkeypatch `FirecrawlApp` and assert rejected URLs never instantiate/call provider.
  - Notes : `search_web(query)` is query-based, not direct URL-fetching, but returned URLs should not be subsequently trusted without validation.

- [ ] Tâche 8 : Apply URL safety to Exa URL tools
  - Fichier : `agents/shared/tools/exa_tools.py`
  - Action : Validate input to `exa_find_similar(url)` and each URL passed to `exa_get_contents(urls)` before provider calls.
  - User story link : Protects content-fetch and similar-page surfaces.
  - Depends on : Tâche 6
  - Validate with : Unit tests that monkeypatch `Exa` and assert private/localhost URLs are rejected before provider calls.
  - Notes : `exa_search(query, ...)` remains query-based; do not over-sanitize normal search queries as URLs.

- [ ] Tâche 9 : Preserve research route runtime behavior
  - Fichier : `api/routers/research.py`, `tests/test_research_router.py`
  - Action : Confirm no adapter work bypasses `ai_runtime_service.preflight_providers`, `bind_provider_env`, `user_llm_service.get_crewai_llm`, or optional Firecrawl gating. Add a regression test if needed.
  - User story link : Keeps app-visible AI behavior stable.
  - Depends on : Tâches 2, 7, 8
  - Validate with : `pytest tests/test_research_router.py`
  - Notes : Do not convert this route to PydanticAI as the first pilot unless the implementation explicitly chooses research post-processing as the pilot flow.

- [ ] Tâche 10 : Migrate one structured-output pilot flow
  - Fichier : `api/services/repo_understanding_service.py` or one file in `agents/psychology/`
  - Action : Route one JSON-heavy flow through the adapter with a typed Pydantic model and deterministic error mapping.
  - User story link : Proves PydanticAI has practical value in the repo instead of remaining a declared-only dependency.
  - Depends on : Tâches 2-5
  - Validate with : focused unit tests for the chosen pilot flow.
  - Notes : Prefer `repo_understanding_service.py` unless implementation discovers a lower-risk psychology flow.

- [ ] Tâche 11 : Verify agent import and fixture health
  - Fichier : `tests/agents/test_research_analyst.py`, `tests/fixtures/agent_fixtures.py`
  - Action : Run relevant tests and repair only migration-related fixture breakage. If stale `get_balanced_llm` patches fail independently, document as pre-existing unless fixing is necessary for migration checks.
  - User story link : Ensures active agent surfaces still import and construct safely.
  - Depends on : Tâches 2, 7, 8, 10
  - Validate with : `pytest tests/agents/test_research_analyst.py tests/test_research_router.py`
  - Notes : Keep lazy imports; avoid requiring provider secrets in unit tests.

- [ ] Tâche 12 : Run dependency and backend checks
  - Fichier : `requirements.txt`, `tests/`
  - Action : Run the smallest reliable checks first, then broader pytest if dependency installation is available.
  - User story link : Demonstrates migration is safe enough to ship.
  - Depends on : Tâches 2-11
  - Validate with : `pytest tests/test_dependency_policy.py tests/test_url_safety.py tests/test_research_router.py tests/agents/test_research_analyst.py` and project dependency install/resolve command.
  - Notes : If dependency installation is impossible in the current environment, capture exact command and failure.

- [ ] Tâche 13 : Update docs/changelog
  - Fichier : `CHANGELOG.md`, optionally `AGENTS.md` or `CLAUDE.md`
  - Action : Document the supported PydanticAI range, the adapter rule, and the first pilot flow migrated.
  - User story link : Keeps future agents from reintroducing dependency/security drift.
  - Depends on : Tâche 12
  - Validate with : Review diff for concise, accurate notes.
  - Notes : Do not update app docs if API contracts do not change.

- [ ] Tâche 14 : Record migration and rollback notes
  - Fichier : PR description or implementation notes; no code file required unless project convention demands it
  - Action : State Turso migration requirement `no`, adapter decision, pilot flow, test results, and rollback command strategy.
  - User story link : Enables safe operational handling.
  - Depends on : Tâche 13
  - Validate with : Final implementation summary includes these notes.
  - Notes : Rollback is dependency-code revert only unless implementation unexpectedly introduces persisted state.

# Acceptance Criteria
- `requirements.txt` no longer contains the stale `pydantic-ai>=0.1.0,<1.0` risk.
- `pydantic-ai` remains an intentional dependency on a supported major line.
- Every direct use goes through `api/services/pydantic_ai_runtime.py` or another explicitly approved adapter, and no route directly constructs PydanticAI provider clients.
- One pilot structured-output flow uses the adapter with a typed output model.
- Existing `POST /api/research/competitor-analysis` tests pass and still assert missing BYOK credentials fail with `409`.
- URL safety tests reject localhost, loopback, private IPv4/IPv6, link-local, metadata IPs, unsupported schemes, userinfo URLs, and malformed URLs before external provider calls.
- Firecrawl/Exa wrapper tests prove rejected URLs do not instantiate or call external clients.
- No app-visible route uses ambient `OPENROUTER_API_KEY` fallback for user-triggered LLM calls.
- No secrets are included in errors or logs introduced by the migration.
- No Turso/libSQL migration is introduced or required; implementation notes explicitly say why.
- `CHANGELOG.md` or equivalent implementation notes document the dependency risk treatment and rollback.

# Test Strategy
Static/policy tests:

- Scan for forbidden `pydantic_ai` imports outside adapter.
- Validate dependency constraint is supported-major-only.
- Scan for deprecated PydanticAI API names if adapter exists: `result_type`, `result_retries`, `result_validator`, `last_run_messages`, `.data` on agent results.

Unit tests:

- `tests/test_dependency_policy.py` for dependency/import policy.
- `tests/test_url_safety.py` for pure URL validation cases.
- Firecrawl wrapper tests with provider monkeypatching.
- Exa wrapper tests with provider monkeypatching.
- Adapter tests for the required PydanticAI runtime adapter.

Route tests:

- `tests/test_research_router.py` to preserve credential behavior, optional Firecrawl handling, request normalization, and response parsing.
- Add a regression test that `include_firecrawl_tools` is false when preflight lacks optional Firecrawl.

Agent tests:

- `tests/agents/test_research_analyst.py` for import/construction smoke coverage.
- Avoid live provider calls; use monkeypatches/mocks.

Install/check commands:

- `python3 -m pytest tests/test_dependency_policy.py tests/test_url_safety.py tests/test_research_router.py tests/agents/test_research_analyst.py`
- Project dependency install/resolve command used by the active environment, for example `python3 -m pip install -r requirements-dev.txt` if permitted and appropriate.
- Full `pytest` only after targeted tests pass and dependencies are available.

Manual verification:

- Review `git diff` to ensure unrelated dependency-file changes from other agents were not overwritten.
- Confirm no changes under `/home/claude/contentflow/contentflow_lab_deploy`.
- Confirm no DB migration files were added.

# Risks
- The dependency may be used by hidden production-only scripts or deployment packaging not visible in the scanned code. Mitigation: full repo scan, import checks, dependency install check, rollback note.
- PydanticAI V2 timing may make target-major selection ambiguous. Mitigation: use official docs/package metadata current at implementation time and keep adapter narrow.
- URL safety can break legitimate competitor analysis for intranet/staging URLs. Mitigation: app-visible external research should not fetch private networks by default; add an explicit future spec for trusted internal crawling if needed.
- DNS-based SSRF checks can be flaky or bypassed via rebinding. Mitigation: validate parsed IPs, reject dangerous host literals, and if resolving DNS, check all resolved addresses immediately before provider call.
- Tests may be limited by missing local dependencies (`pydantic-ai`, `crewai`). Mitigation: separate static/unit tests from runtime integration checks and report environment gaps.
- Introducing an adapter could increase maintenance surface if not actually needed. Mitigation: skip adapter unless direct usage is confirmed.
- Existing stale fixtures may fail unrelated to this migration. Mitigation: fix only when required for migration acceptance or document as pre-existing.

# Execution Notes
- Current date for this spec: 2026-04-27.
- Official PydanticAI docs were checked during spec creation because SDK behavior and version policy are temporally unstable.
- PydanticAI Upgrade Guide source: https://pydantic.dev/docs/ai/project/changelog/
- PydanticAI Version Policy source: https://pydantic.dev/docs/ai/project/version-policy/
- PydanticAI OpenRouter source: https://pydantic.dev/docs/ai/models/openrouter/
- PydanticAI Dependencies source: https://pydantic.dev/docs/ai/core-concepts/dependencies/
- PydanticAI Function Tools source: https://pydantic.dev/docs/ai/tools-toolsets/tools/
- At spec time, `rg -n "from pydantic_ai|import pydantic_ai|pydantic_ai" agents api tests` returned no matches.
- At spec time, `python3` metadata reported `pydantic-ai: not installed`, `pydantic==2.12.5`, `fastapi==0.116.1`, and `crewai: not installed` in the current shell environment.
- At spec time, `requirements.txt` and `requirements-dev.txt` were already dirty/untracked in the workspace; implementation must inspect and preserve those changes.
- Turso migration required: no, because this is dependency/runtime/tool-safety work with no planned schema/table/column/index changes.
- Rollback: revert the dependency/test/adapter/pilot changes from the migration commit. If the adapter path was added behind a flag, disable the flag first, then revert.
- Incremental order: inventory, dependency range update, adapter, pilot flow, policy test, URL guard, wrapper application, route regression tests, docs/rollback note.

# Open Questions
- Assumption locked for implementation: direct `pydantic_ai` usage remains absent until the adapter/pilot work introduces it.
- Assumption locked for implementation: preferred resolution is adapter-based introduction, not removal.
- Assumption locked for implementation: URL safety can reject private/internal URLs for app-visible research tools without breaking the intended product contract.
- Assumption locked for implementation: no Turso migration is needed.
- Assumption locked for implementation: exact supported PydanticAI major/range must be verified again from official docs/package metadata at implementation time because April 2026 is within the documented earliest V2 window.
