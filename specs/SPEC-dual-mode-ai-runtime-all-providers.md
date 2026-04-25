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
next_step: "/sf-docs audit specs/SPEC-dual-mode-ai-runtime-all-providers.md"
---
# Title
Dual-Mode AI Runtime For User-Triggered AI Providers

## Status
ready

## Problem
The product direction is no longer “strict OpenRouter BYOK only”. ContentFlow now needs one coherent architecture that supports two commercial modes for user-triggered AI workflows:

- `byok`: the user pays providers directly with their own keys
- `platform`: ContentFlow pays providers and will monetize usage later through plans or credits

The current codebase is not ready for that model:

- the existing BYOK work is still OpenRouter-specific in both API and Flutter settings
- user-triggered routes still mix direct env reads, implicit provider defaults, and singleton agent caches
- Mem0-backed paths still reintroduce env-based LLM usage through `OPENROUTER_API_KEY`
- newsletter memory is not consistently scoped by `user_id` and `project_id`
- the app still interprets any `409` as “OpenRouter missing”, which is unsafe once runtime errors and normal business conflicts coexist

Without one runtime policy and one resolver, ContentFlow cannot safely support:

- BYOK pay-as-you-go
- platform-paid usage
- stable billing semantics across the same workflow
- clean removal of accidental env fallback in covered routes

## Solution
Introduce a single backend AI runtime policy and resolver for every user-triggered AI workflow covered by this spec.

Each request resolves one runtime context before any provider call:

- `mode = byok`: use user-managed encrypted credentials from `UserProviderCredential`
- `mode = platform`: use operator-managed secrets, gated by an entitlement decision

For V1, the `platform` entitlement source is explicit and deterministic:

- global feature flag: `AI_PLATFORM_MODE_ENABLED`
- user allowlist: `AI_PLATFORM_MODE_ALLOWED_USER_IDS`

Rules:

- `AI_PLATFORM_MODE_ENABLED` defaults to `false`
- when `AI_PLATFORM_MODE_ENABLED != true`, no user is entitled
- when `AI_PLATFORM_MODE_ENABLED == true`, a user is entitled only if their `user_id` is present in `AI_PLATFORM_MODE_ALLOWED_USER_IDS`
- the entitlement gate reads this env-backed policy on each request; it is not stored in `UserSettings`
- `UserSettings.robotSettings.aiRuntime.mode` only stores the user’s selected mode after entitlement has already been approved

The resolved runtime context is then injected into routers, services, crews, tools, and memory-backed code. Covered routes must never decide credentials by reading provider env vars directly.

### Route-To-Provider Matrix
This matrix is the canonical contract for V1.

- `POST /api/personas/draft`
  - `mode == blank_form`: no AI provider required
  - `repo_source == project_repo` or `connected_github`: required `openrouter`
  - `repo_source == manual_url` and URL is GitHub: required `openrouter`
  - `repo_source == manual_url` and URL is non-GitHub: required `openrouter` + `firecrawl`
  - Failure behavior: hard fail before job creation if a required provider is unavailable in the selected mode

- `POST /api/psychology/synthesize-narrative`
  - required `openrouter`
  - optional providers: none
  - Failure behavior: hard fail before job creation

- `POST /api/psychology/refine-persona`
  - required `openrouter`
  - optional providers: none
  - Failure behavior: hard fail before job creation

- `POST /api/psychology/generate-angles`
  - required `openrouter`
  - optional providers: none
  - Failure behavior: hard fail before job creation

- `POST /api/psychology/dispatch-pipeline` with `target_format == article`
  - required `openrouter` + `exa`
  - optional `firecrawl`
  - optional Mem0 context load/store
  - Failure behavior:
    - missing required provider: hard fail before job creation
    - missing optional `firecrawl`: inject a tool profile without Firecrawl tools
    - missing optional Mem0 runtime: continue with memory disabled

- `POST /api/psychology/dispatch-pipeline` with `target_format == newsletter`
  - required `openrouter` + `exa`
  - operator-managed email backend not required in V1 for angle-to-newsletter generation
  - optional Mem0 context load/store
  - Failure behavior:
    - missing required provider: hard fail before job creation
    - missing optional Mem0 runtime: continue with memory disabled
  - Implementation rule: this path must use a no-email newsletter generation profile and must not implicitly read inbox tools

- `POST /api/psychology/dispatch-pipeline` with `target_format == short`
  - required `openrouter`
  - optional Mem0 store
  - Failure behavior: missing Mem0 does not block generation

- `POST /api/psychology/dispatch-pipeline` with `target_format == social_post`
  - required `openrouter`
  - optional Mem0 store
  - Failure behavior: missing Mem0 does not block generation

- `POST /api/newsletter/generate`
  - required `openrouter` + `exa`
  - request switch: body field `include_email_insights: boolean`, default `true`
  - conditional operator-managed email backend when `include_email_insights == true`
  - optional Mem0 context load/store
  - Failure behavior:
    - missing required provider: hard fail
    - missing email backend: hard fail only when `include_email_insights == true`
    - missing optional Mem0 runtime: continue with memory disabled

- `POST /api/newsletter/generate-async`
  - same provider rules as synchronous newsletter generation
  - same `include_email_insights: boolean` request field, default `true`

- `POST /api/research/competitor-analysis`
  - required `openrouter` + `exa`
  - optional `firecrawl`
  - Failure behavior:
    - missing required provider: hard fail
    - missing optional `firecrawl`: inject a tool profile without Firecrawl tools
    - route must not swallow provider/runtime failures into empty `200` payloads

- `POST /api/mesh/analyze`
  - out of scope for this spec
  - reason: the app-visible path is repo/site structure analysis, not a runtime-selected AI provider workflow today

### Runtime Contract
The runtime policy remains per-user in V1 and defaults to `byok` when unset.

The persisted selection and the effective authorization are distinct:

- `robotSettings.aiRuntime.mode` stores the user’s selected mode
- every covered request must re-check entitlement before resolving `platform`
- if `platform` was previously persisted but the entitlement env policy later revokes access, the stored mode remains `platform` but:
  - covered requests fail with `ai_runtime_platform_not_entitled`
  - `GET /api/settings/ai-runtime` shows `platform` as unavailable for the current user
  - there is no automatic fallback to `byok`

`GET /api/settings/ai-runtime` returns:

```json
{
  "mode": "byok",
  "availableModes": [
    {
      "mode": "byok",
      "enabled": true,
      "reasonCode": null,
      "message": null
    },
    {
      "mode": "platform",
      "enabled": false,
      "reasonCode": "platform_not_entitled",
      "message": "Platform-paid mode is not enabled for this account."
    }
  ],
  "providers": [
    {
      "provider": "openrouter",
      "kind": "llm",
      "usedBy": [
        "personas.draft",
        "psychology.synthesize_narrative",
        "psychology.refine_persona",
        "psychology.generate_angles",
        "psychology.dispatch_pipeline.article",
        "psychology.dispatch_pipeline.newsletter",
        "psychology.dispatch_pipeline.short",
        "psychology.dispatch_pipeline.social_post",
        "newsletter.generate",
        "research.competitor_analysis"
      ],
      "byok": {
        "supported": true,
        "configured": true,
        "maskedSecret": "••••••••abcd",
        "validationStatus": "valid",
        "canValidate": true
      },
      "platform": {
        "supported": true,
        "configured": true,
        "available": false,
        "reasonCode": "platform_not_entitled"
      }
    }
  ]
}
```

The real response must include provider entries for `openrouter`, `exa`, and `firecrawl`, even if the example above only expands one item.

Provider-branch semantics in the runtime response:

- `byok.supported`: the product supports user-managed credentials for that provider in V1
- `byok.configured`: a user-managed credential exists for the current user
- `platform.supported`: the product supports operator-paid use of that provider in V1
- `platform.configured`: the operator-side provider wiring exists on the server for that provider
  - secret present
  - required SDK/client setup available
- `platform.available`: `platform.supported && platform.configured && current_user_is_entitled`
- deleting a BYOK credential changes only the `byok.*` branch
- operator outages or missing operator secrets never mutate `byok.*`

### Newsletter Readiness Contract
`GET /api/newsletter/config/check` is preserved in V1 as a compatibility endpoint for the current Flutter screen. It is not replaced by `GET /api/settings/ai-runtime` in this iteration.

The endpoint gains one optional query parameter:

- `include_email_insights: boolean = true`

Its contract remains:

```json
{
  "configured": false,
  "ready": false,
  "llm_configured": false,
  "server_ready": false,
  "checks": {
    "openrouter_configured": false,
    "exa_configured": false,
    "imap_configured": false,
    "composio_configured": false,
    "sendgrid_configured": false
  },
  "instructions": {
    "exa": "Set EXA_API_KEY in environment",
    "composio": "Run: composio add gmail",
    "sendgrid": "Set SENDGRID_API_KEY for sending"
  }
}
```

Semantics for V1:

- the endpoint reports readiness for the standalone newsletter route only, not `dispatch-pipeline`
- the endpoint must evaluate readiness for the exact standalone request shape selected by `include_email_insights`
- when `include_email_insights=true`:
  - `llm_configured` means the current runtime mode satisfies the standalone newsletter route AI-provider requirements
  - `server_ready` means the operator-managed inbox/email dependencies required for email-insight generation are available
- when `include_email_insights=false`:
  - `llm_configured` uses the same AI-provider logic
  - `server_ready` ignores inbox/email-insight dependencies and only reflects the remaining operator-managed dependencies needed for a no-email standalone newsletter run
- `configured` and `ready` both mean `llm_configured && server_ready`
- this compatibility route must not be used by Flutter as the source of truth for global AI mode selection; it remains newsletter-specific only
- the standalone newsletter route must support both execution profiles:
  - email profile: inbox tools available
  - no-email profile: inbox tools excluded from the agent tool list
- `dispatch-pipeline` newsletter always uses the no-email profile

Readiness truth table for V1:

| `include_email_insights` | `llm_configured` | `server_ready` | `configured` / `ready` |
|---|---|---|---|
| `true` | current mode satisfies `openrouter` + `exa` for standalone newsletter generation | `imap_configured || composio_configured` | `llm_configured && server_ready` |
| `false` | current mode satisfies `openrouter` + `exa` for standalone newsletter generation | `true` | `llm_configured && server_ready` |

Rules for `checks`:

- `checks` is never filtered; it always returns all five keys defined in this spec
- `openrouter_configured` and `exa_configured` reflect runtime-mode-specific provider readiness for the standalone newsletter route
- `imap_configured`, `composio_configured`, and `sendgrid_configured` reflect raw operator dependency state
- `sendgrid_configured` is informational only in V1 for newsletter generation and does not participate in `server_ready`

`PUT /api/settings/ai-runtime` accepts:

```json
{
  "mode": "byok"
}
```

Valid request values in V1:

- `{"mode":"byok"}`
- `{"mode":"platform"}`

Response contract:

- on success, `PUT /api/settings/ai-runtime` returns the same payload shape as `GET /api/settings/ai-runtime`, with the persisted effective mode
- if `mode = "platform"` and the user is not entitled, the backend must not persist the change and must return:
  - HTTP `403`
  - `code = ai_runtime_platform_not_entitled`
  - `kind = ai_runtime`
- if `mode = "platform"` and the user is entitled, the backend persists `platform`
- if `mode = "byok"`, the backend always persists `byok`
- unavailable modes must never be persisted optimistically

`GET|PUT|DELETE /api/settings/integrations/{provider}` use one generic provider status contract:

```json
{
  "provider": "exa",
  "configured": true,
  "maskedSecret": "••••••••abcd",
  "validationStatus": "unknown",
  "lastValidatedAt": null,
  "updatedAt": "2026-04-23T00:00:00Z"
}
```

When no user-managed credential exists, `GET /api/settings/integrations/{provider}` returns:

```json
{
  "provider": "exa",
  "configured": false,
  "maskedSecret": null,
  "validationStatus": "unknown",
  "lastValidatedAt": null,
  "updatedAt": null
}
```

`PUT /api/settings/integrations/{provider}` uses this canonical request body:

```json
{
  "secret": "provider-secret-value"
}
```

Compatibility aliases accepted in V1:

- `secret`
- `apiKey`
- `api_key`

Behavior rules:

- `provider` must be one of `openrouter`, `exa`, or `firecrawl`
- `PUT` upserts the user-managed secret for that provider and returns the generic provider status payload
- `openrouter` stores `validationStatus = "unknown"` on write and supports explicit validation via `POST /api/settings/integrations/openrouter/validate`
- `exa` and `firecrawl` store `validationStatus = "unknown"` on write and do not have dedicated validate endpoints in V1
- unsupported providers must return:
  - HTTP `400`
  - `code = ai_runtime_provider_not_supported`
  - `kind = ai_runtime`
- empty or clearly invalid bodies must return a normal request-validation `400`, not an AI runtime error

`DELETE /api/settings/integrations/{provider}` is idempotent and returns:

```json
{
  "deleted": true,
  "provider": "exa"
}
```

Rules:

- deleting a non-existent user credential still returns `deleted: true`
- deleting a BYOK credential never changes `platform` mode availability

V1 provider validation buttons:

- `openrouter`: yes
- `exa`: no dedicated validate endpoint in V1
- `firecrawl`: no dedicated validate endpoint in V1

### Error Contract
AI runtime errors must use a machine-readable envelope in `HTTPException.detail`:

```json
{
  "code": "ai_runtime_user_credential_missing",
  "message": "OpenRouter is required in BYOK mode for this action.",
  "kind": "ai_runtime",
  "mode": "byok",
  "provider": "openrouter",
  "route": "psychology.generate_angles",
  "settingsPath": "/settings?section=ai-runtime",
  "retryable": false
}
```

Required fields for all AI runtime errors:

- `code: string`
- `message: string`
- `kind: "ai_runtime"`
- `route: string`
- `retryable: boolean`

Optional nullable fields:

- `mode: "byok" | "platform" | null`
- `provider: "openrouter" | "exa" | "firecrawl" | null`
- `settingsPath: string | null`
- `details: object | null`

Rules:

- `route` is always required, even when the error happens in a shared service
- `provider` is required when the error is tied to one concrete provider, otherwise `null`
- `mode` is required when runtime mode was successfully resolved, otherwise `null`
- `settingsPath` is required for user-actionable configuration errors and may be `null` for operator/runtime outages
- `details` is reserved for structured provider-specific context and must never contain secrets
- provider outages after work has already started may still surface as route-specific failures, but request-time preflight should prefer the canonical runtime codes below whenever the failure is classifiable early

Canonical codes for V1:

- `ai_runtime_user_credential_missing`
- `ai_runtime_user_credential_invalid`
- `ai_runtime_provider_not_supported`
- `ai_runtime_platform_not_entitled`
- `ai_runtime_operator_provider_missing`
- `ai_runtime_operator_provider_unavailable`
- `ai_runtime_request_not_supported`

HTTP status mapping for V1:

- `ai_runtime_user_credential_missing` -> `409`
- `ai_runtime_user_credential_invalid` -> `409`
- `ai_runtime_provider_not_supported` -> `400`
- `ai_runtime_platform_not_entitled` -> `403`
- `ai_runtime_operator_provider_missing` -> `503`
- `ai_runtime_operator_provider_unavailable` -> `503`
- `ai_runtime_request_not_supported` -> `400`

Emit rules for canonical AI runtime codes:

- `ai_runtime_user_credential_missing`
  - emit when the active route matrix requires a BYOK provider and no user-managed credential exists for that provider
- `ai_runtime_user_credential_invalid`
  - emit when the active route matrix requires a BYOK provider and the stored credential exists but has `validationStatus = "invalid"`
- `ai_runtime_provider_not_supported`
  - emit when the route or settings API is asked to use a provider outside the V1 provider set
- `ai_runtime_platform_not_entitled`
  - emit when `platform` is selected or requested and the current request-time entitlement check fails
- `ai_runtime_operator_provider_missing`
  - emit when `platform` is active and the required operator-side provider wiring is absent before work starts
- `ai_runtime_operator_provider_unavailable`
  - emit when `platform` is active, wiring exists, but the provider cannot be reached or initialized cleanly before useful work can proceed
- `ai_runtime_request_not_supported`
  - emit when the requested route/mode/profile combination is explicitly unsupported by the route matrix in this spec

Non-runtime business conflicts must not reuse these codes. Example:

- duplicate content in `dispatch-pipeline` must return a distinct code such as `content_duplicate_conflict`

Business conflicts must use a separate envelope:

```json
{
  "code": "content_duplicate_conflict",
  "message": "Similar content already exists.",
  "kind": "business_conflict",
  "route": "psychology.dispatch_pipeline",
  "retryable": false,
  "details": {
    "existingContentId": "abc123",
    "existingTitle": "Existing article"
  }
}
```

Flutter runtime guards must branch on `kind == "ai_runtime"` or `code` prefix, never on HTTP status alone.

Newsletter dependency failures must use a separate non-runtime envelope:

```json
{
  "code": "newsletter_email_backend_missing",
  "message": "Email insights require IMAP or Composio to be configured.",
  "kind": "dependency",
  "route": "newsletter.generate",
  "retryable": false,
  "details": {
    "includeEmailInsights": true,
    "requiredAnyOf": ["imap", "composio"]
  }
}
```

HTTP status mapping:

- `newsletter_email_backend_missing` -> `503`

Flutter must not parse `kind == "dependency"` as an AI runtime setup error.

## Scope In
- A persisted per-user AI runtime policy in `UserSettings.robotSettings.aiRuntime`
- Generic provider credential management for user-triggered AI providers:
  - `openrouter`
  - `exa`
  - `firecrawl`
- A centralized runtime resolver that supports both `byok` and `platform`
- A backend entitlement layer for `platform` mode, without billing implementation
- Request-scoped provider injection for:
  - persona draft
  - psychology routes
  - newsletter generation and readiness
  - research competitor analysis
- Tool-profile injection so optional providers such as `firecrawl` can be disabled cleanly instead of failing inside tools
- Removal of env fallback from covered routes and covered memory-backed paths
- User/project-scoped newsletter memory reads and writes
- Flutter settings UI for runtime mode and provider readiness
- Flutter runtime-error handling based on error codes, not raw HTTP status
- Regression coverage for mixed-mode isolation and no-env-fallback behavior

## Scope Out
- Billing, credits, Polar integration, invoices, or pricing display
- Workspace-shared runtime policy
- BYOK support for pure infrastructure providers:
  - GitHub OAuth
  - IMAP/Composio
  - SendGrid
  - Bunny
  - Turso
- Non-user-triggered background jobs such as scheduler agents
- Direct multi-LLM vendor support beyond `openrouter` in V1
- `POST /api/mesh/analyze`, `build`, `improve`, `compare`, and websocket mesh streaming
- Legacy template-generation endpoints not used by the current Flutter app
- Removing operator-managed secrets from deployment config for `platform` mode

## Constraints
- The runtime policy is per-user only in V1.
- The default mode is `byok` when `robotSettings.aiRuntime` is absent.
- `platform` entitlement is env-backed in V1:
  - `AI_PLATFORM_MODE_ENABLED`
  - `AI_PLATFORM_MODE_ALLOWED_USER_IDS`
- Covered routes must resolve runtime through one centralized service before any provider call.
- Covered routes must not read `OPENROUTER_API_KEY`, `EXA_API_KEY`, `FIRECRAWL_API_KEY`, `GROQ_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY` directly.
- Operator env secrets are allowed only inside the centralized `platform` branch.
- A request may not silently fall back from `byok` to `platform`, or from `platform` to `byok`.
- Every covered request must revalidate `platform` entitlement at request time, even if `platform` is already persisted in `UserSettings`.
- Optional providers must be removed from the tool profile when unavailable; they must not remain registered and fail lazily at tool execution time.
- Missing optional Mem0 runtime must degrade to “memory disabled”, not to env fallback.
- `blank_form` persona draft remains a non-LLM exception path.
- No raw secret may be written to API responses, logs, jobs, content metadata, or memory metadata.
- `platform` mode must remain hidden or disabled until the entitlement layer allows it.
- standalone newsletter generation selects inbox-enabled vs no-email execution through request body field `include_email_insights`, default `true`

## Dependencies
- Backend persistence and models:
  - `contentflow_lab/api/services/user_key_store.py`
  - `contentflow_lab/api/services/user_data_store.py`
  - `contentflow_lab/api/models/user_data.py`
- Backend routing and services:
  - `contentflow_lab/api/routers/settings_integrations.py`
  - `contentflow_lab/api/routers/personas.py`
  - `contentflow_lab/api/routers/psychology.py`
  - `contentflow_lab/api/routers/newsletter.py`
  - `contentflow_lab/api/routers/research.py`
  - `contentflow_lab/api/services/user_llm_service.py`
  - `contentflow_lab/api/services/repo_understanding_service.py`
- Shared provider tools:
  - `contentflow_lab/agents/shared/tools/exa_tools.py`
  - `contentflow_lab/agents/shared/tools/firecrawl_tools.py`
  - `contentflow_lab/agents/newsletter/tools/content_tools.py`
  - `contentflow_lab/agents/newsletter/tools/gmail_tools.py`
  - `contentflow_lab/agents/newsletter/tools/imap_tools.py`
- Memory:
  - `contentflow_lab/memory/memory_config.py`
  - `contentflow_lab/memory/memory_service.py`
  - `contentflow_lab/agents/newsletter/newsletter_agent.py`
  - `contentflow_lab/agents/newsletter/newsletter_crew.py`
  - `contentflow_lab/agents/newsletter/tools/memory_tools.py`
- Flutter:
  - `contentflow_app/lib/data/models/app_settings.dart`
  - `contentflow_app/lib/data/models/openrouter_credential.dart`
  - `contentflow_app/lib/data/services/api_service.dart`
  - `contentflow_app/lib/presentation/screens/settings/settings_screen.dart`
  - `contentflow_app/lib/core/openrouter_guard.dart`

## Invariants
- Every covered request resolves exactly one runtime context before any provider call.
- Required providers hard-fail before work starts.
- Optional providers are omitted from runtime tool profiles when unavailable.
- No user-bound LLM, provider client, or agent instance is cached across users.
- Memory-backed paths never recover by reading provider env vars directly.
- Newsletter memory reads and writes remain scoped by `user_id` and, when available, `project_id`.
- `dispatch-pipeline` remains the single owner of the canonical content record.
- Older OpenRouter-only settings endpoints may remain as compatibility aliases during rollout, but they must delegate to the generic runtime and integrations contract.

## Links & Consequences
- This spec supersedes [SPEC-strict-byok-llm-app-visible-ai.md](/home/claude/contentflow/contentflow_lab/specs/SPEC-strict-byok-llm-app-visible-ai.md:1).
- `user_llm_service.py` must either become a thin adapter over a new generic runtime service or be replaced by it.
- `repo_understanding_service.py` must switch from direct Firecrawl env reads to runtime-injected Firecrawl access for non-GitHub `manual_url`.
- `research.py` must stop swallowing provider/runtime failures into empty success payloads.
- The Flutter app must stop modeling AI setup as one OpenRouter card and one `statusCode == 409` heuristic.
- Newsletter email integrations remain operator-managed in both modes; this is intentional and not part of BYOK.
- `dispatch-pipeline` for newsletter must not implicitly depend on inbox/email integrations; only the standalone newsletter route may do so.
- `mesh/analyze` stays on its current contract because it is not an AI-runtime-selected path in the app today.
- `GET /api/newsletter/config/check` remains in V1 as a compatibility route and must be reimplemented on top of the dual-mode runtime contract rather than removed silently.
- The standalone newsletter route must expose two deterministic execution profiles keyed by `include_email_insights`: inbox-enabled and inbox-disabled.

## Edge Cases
- User switches from `platform` to `byok` with no provider credentials configured.
- User switches from `byok` to `platform` but is not entitled.
- User has `openrouter` configured but not `exa`, then triggers article/newsletter/research.
- User has `openrouter` configured and `exa` configured, but no `firecrawl`, then triggers a route where Firecrawl is optional.
- Persona draft uses `manual_url` with a public non-GitHub URL in `byok` mode and the user has no Firecrawl key.
- Newsletter generation enables email insights but the operator email backend is not configured.
- Newsletter generation disables email insights and must still run without email backend.
- `dispatch-pipeline` newsletter must generate from the angle without inbox access.
- Mem0 local or hosted runtime is unavailable; generation must continue without memory instead of failing open.
- Older Flutter build still calls `/api/settings/integrations/openrouter`.

## Implementation Tasks
- [ ] Task 1: Define typed AI runtime models and the canonical error envelope
  - File: `contentflow_lab/api/models/ai_runtime.py`, `contentflow_lab/api/models/user_data.py`
  - Action: Create typed models for runtime mode, available modes, provider status, credential status, and machine-readable runtime errors; update `api/models/user_data.py` only as needed to embed `aiRuntime` inside user settings
  - Depends on: none
  - Validate with: `pytest tests/test_ai_runtime_models.py`
  - Notes: The JSON shapes in this spec are the source of truth

- [ ] Task 2: Persist `robotSettings.aiRuntime` cleanly in the settings store
  - File: `contentflow_lab/api/services/user_data_store.py`
  - Action: Merge `aiRuntime` without clobbering unrelated `robotSettings` keys and expose a helper for resolving the effective runtime mode when unset
  - Depends on: Task 1
  - Validate with: `pytest tests/test_user_data_store_ai_runtime.py`
  - Notes: Default to `byok` when no runtime policy is stored

- [ ] Task 3: Add the platform-mode entitlement service
  - File: `contentflow_lab/api/services/ai_entitlement_service.py`
  - Action: Implement one backend gate that decides whether `platform` mode is available for a given user, using V1 env-backed policy from `AI_PLATFORM_MODE_ENABLED` and `AI_PLATFORM_MODE_ALLOWED_USER_IDS`
  - Depends on: Task 1
  - Validate with: `pytest tests/test_ai_entitlement_service.py`
  - Notes: Billing is out of scope; this is only the availability gate; the selected mode is persisted separately in `UserSettings`

- [ ] Task 4: Build the centralized AI runtime resolver
  - File: `contentflow_lab/api/services/ai_runtime_service.py`
  - Action: Resolve `byok` vs `platform`, load required provider credentials, construct request-scoped OpenRouter/Exa/Firecrawl clients, expose optional-provider tool profiles, and emit canonical runtime errors
  - Depends on: Tasks 1, 2, and 3
  - Validate with: `pytest tests/test_ai_runtime_service.py`
  - Notes: This service becomes the only valid place to read operator AI provider env vars

- [ ] Task 5: Replace the OpenRouter-only settings surface with the generic runtime and provider API
  - File: `contentflow_lab/api/routers/settings_integrations.py`, `contentflow_lab/api/models/ai_runtime.py`
  - Action: Add `GET|PUT /api/settings/ai-runtime` plus generic `/api/settings/integrations/{provider}` endpoints, while preserving temporary `/openrouter` aliases for backward compatibility
  - Depends on: Tasks 1, 2, 3, and 4
  - Validate with: `pytest tests/test_settings_ai_runtime_router.py`
  - Notes: Provider payloads and error codes must match the spec exactly

- [ ] Task 6: Make provider tools runtime-injectable and support optional-provider tool profiles
  - File: `contentflow_lab/agents/shared/tools/exa_tools.py`, `contentflow_lab/agents/shared/tools/firecrawl_tools.py`, `contentflow_lab/agents/newsletter/tools/content_tools.py`
  - Action: Refactor shared Exa and Firecrawl tools so covered agents can be built with required providers and with optional providers removed from the tool list instead of left as broken env-driven tools
  - Depends on: Task 4
  - Validate with: `pytest tests/test_provider_tools_runtime.py`
  - Notes: Update `firecrawl_tools.py`, `agents/newsletter/tools/content_tools.py`, and any helper needed for tool-profile assembly

- [ ] Task 7: Remove Mem0 env fallback and make memory behavior explicit
  - File: `contentflow_lab/memory/memory_config.py`, `contentflow_lab/memory/memory_service.py`
  - Action: Stop binding Mem0 LLM extraction to `OPENROUTER_API_KEY` at import time; add runtime-aware configuration entrypoints and a clean “memory disabled” path when no safe runtime is available
  - Depends on: Task 4
  - Validate with: `pytest tests/test_memory_runtime_scoping.py`
  - Notes: Update `memory_service.py` together with the config layer

- [ ] Task 8: Migrate persona draft to the generic runtime matrix
  - File: `contentflow_lab/api/routers/personas.py`, `contentflow_lab/api/services/repo_understanding_service.py`
  - Action: Replace OpenRouter-specific gating with runtime preflight and update `api/services/repo_understanding_service.py` so manual non-GitHub URLs use runtime-injected Firecrawl instead of env fallback
  - Depends on: Tasks 4 and 6
  - Validate with: `pytest tests/test_persona_draft_route.py`
  - Notes: Preserve `blank_form` as a non-LLM exception

- [ ] Task 9: Migrate psychology narrative and angle routes to the generic runtime
  - File: `contentflow_lab/api/routers/psychology.py`
  - Action: Resolve runtime before `synthesize-narrative`, `refine-persona`, and `generate-angles`, using the route matrix in this spec
  - Depends on: Task 4
  - Validate with: `pytest tests/test_psychology_auth_jobs.py`
  - Notes: These three routes require only `openrouter`

- [ ] Task 10: Migrate `dispatch-pipeline` by target format
  - File: `contentflow_lab/api/routers/psychology.py`, `contentflow_lab/agents/seo/seo_crew.py`, `contentflow_lab/agents/newsletter/newsletter_agent.py`, `contentflow_lab/agents/newsletter/newsletter_crew.py`, `contentflow_lab/agents/newsletter/tools/gmail_tools.py`, `contentflow_lab/agents/newsletter/tools/imap_tools.py`, `contentflow_lab/agents/short/short_crew.py`, `contentflow_lab/agents/social/social_crew.py`
  - Action: Apply the per-format runtime matrix for `article`, `newsletter`, `short`, and `social_post`; keep duplicate-content conflicts distinct from runtime errors; preserve the single canonical content record; extract the shared newsletter execution-profile builder and implement the dedicated no-email profile used by the pipeline path
  - Depends on: Tasks 4, 6, and 7
  - Validate with: `pytest tests/test_dispatch_pipeline_runtime.py`
  - Notes: `article` and `newsletter` must no longer rely on hidden provider defaults inside their crews; `NewsletterResearchAgent` tool assembly must be made explicit for email vs no-email profiles

- [ ] Task 11: Fix newsletter standalone generation, readiness, and memory scoping
  - File: `contentflow_lab/api/routers/newsletter.py`, `contentflow_lab/agents/newsletter/newsletter_agent.py`, `contentflow_lab/agents/newsletter/newsletter_crew.py`, `contentflow_lab/agents/newsletter/tools/gmail_tools.py`, `contentflow_lab/agents/newsletter/tools/imap_tools.py`, `contentflow_lab/agents/newsletter/tools/memory_tools.py`, `contentflow_lab/agents/newsletter/config/newsletter_config.py`
  - Action: Enforce the newsletter provider matrix, make request body field `include_email_insights` choose between inbox-enabled and no-email profiles for standalone generation, preserve `/api/newsletter/config/check` as a compatibility endpoint with the V1 contract defined in this spec, and thread `user_id` and `project_id` into newsletter memory paths
  - Depends on: Tasks 4, 6, 7, and 10
  - Validate with: `pytest tests/test_newsletter_router.py tests/test_newsletter_memory_scoping.py`
  - Notes: Covered newsletter flows must stop using unscoped `load_context()` and `store_generation()`; the standalone route and the dispatch-pipeline route must not share the same inbox profile by accident

- [ ] Task 12: Migrate research to the generic runtime and stop swallowing provider failures
  - File: `contentflow_lab/api/routers/research.py`, `contentflow_lab/agents/seo/research_analyst.py`
  - Action: Resolve runtime using the route matrix, inject optional-provider tool profiles, and return explicit provider/runtime failures instead of empty successful responses
  - Depends on: Tasks 4 and 6
  - Validate with: `pytest tests/test_research_router.py`
  - Notes: `openrouter` and `exa` are required; `firecrawl` is optional

- [ ] Task 13: Generalize Flutter models and API client to the runtime contract
  - File: `contentflow_app/lib/data/services/api_service.dart`, `contentflow_app/lib/data/models/app_settings.dart`, `contentflow_app/lib/data/models/ai_runtime.dart`
  - Action: Add methods for `GET|PUT /api/settings/ai-runtime` and generic provider integrations, plus Flutter models for runtime mode, available modes, provider statuses, and structured AI runtime errors
  - Depends on: Task 5
  - Validate with: `flutter test test/data/api_service_ai_runtime_test.dart`
  - Notes: `AppSettings` must carry `robotSettings['aiRuntime']`

- [ ] Task 14: Replace the OpenRouter-only Settings UI with a dual-mode runtime UI
  - File: `contentflow_app/lib/presentation/screens/settings/settings_screen.dart`, `contentflow_app/lib/data/models/ai_runtime.dart`
  - Action: Add a runtime mode selector, provider status cards, platform locked states, and migration-safe compatibility for older OpenRouter-only flows
  - Depends on: Task 13
  - Validate with: `flutter test test/presentation/settings/ai_runtime_settings_test.dart`
  - Notes: The UI must not promise billing behavior or pricing

- [ ] Task 15: Replace broad `409` heuristics with structured runtime-error handling in Flutter
  - File: `contentflow_app/lib/core/openrouter_guard.dart`, `contentflow_app/lib/presentation/screens/ritual/ritual_screen.dart`, `contentflow_app/lib/presentation/screens/angles/angles_screen.dart`, `contentflow_app/lib/presentation/screens/newsletter/newsletter_screen.dart`, `contentflow_app/lib/presentation/screens/research/research_screen.dart`
  - Action: Replace the current `statusCode == 409` check with parsing of the formal `kind/code` error envelope defined in this spec, then update the covered screens that surface provider/mode setup errors
  - Depends on: Tasks 5 and 13
  - Validate with: `flutter test test/core/ai_runtime_guard_test.dart`
  - Notes: Duplicate-content conflicts and newsletter non-runtime configuration errors must no longer be misclassified as missing-provider runtime errors

- [ ] Task 16: Add regression coverage and mark the previous strict-BYOK spec as superseded
  - File: `contentflow_lab/tests/test_persona_draft_route.py`, `contentflow_lab/tests/test_psychology_auth_jobs.py`, `contentflow_lab/tests/test_dispatch_pipeline_runtime.py`, `contentflow_lab/tests/test_newsletter_router.py`, `contentflow_lab/tests/test_newsletter_memory_scoping.py`, `contentflow_lab/tests/test_research_router.py`, `contentflow_lab/specs/SPEC-strict-byok-llm-app-visible-ai.md`
  - Action: Add mixed-mode, mixed-user, no-env-fallback, and optional-provider tests across backend routes, then add a superseded note to the previous strict-BYOK spec
  - Depends on: Tasks 8, 9, 10, 11, and 12
  - Validate with: `pytest tests/test_persona_draft_route.py tests/test_psychology_auth_jobs.py tests/test_dispatch_pipeline_runtime.py tests/test_newsletter_router.py tests/test_newsletter_memory_scoping.py tests/test_research_router.py`
  - Notes: Include dummy env vars in tests to prove they are ignored on covered routes

## Acceptance Criteria
- [ ] CA 1: Given a new authenticated user with no stored runtime policy, when they open AI runtime settings, then the effective mode is `byok`.
- [ ] CA 2: Given a user in `byok` mode without an OpenRouter key, when they trigger narrative synthesis, persona refinement, angle generation, short generation, or social generation, then the backend returns `code = ai_runtime_user_credential_missing` before job creation.
- [ ] CA 3: Given a user in `byok` mode without an Exa key, when they trigger article generation, newsletter generation, or research competitor analysis, then the backend returns `code = ai_runtime_user_credential_missing` for `provider = exa` before work starts.
- [ ] CA 4: Given a user in `byok` mode without a Firecrawl key, when they trigger persona draft with a non-GitHub `manual_url`, then the backend returns `code = ai_runtime_user_credential_missing` for `provider = firecrawl`.
- [ ] CA 5: Given a user in `byok` mode without a Firecrawl key, when they trigger article or research routes where Firecrawl is optional, then the route still runs using a Firecrawl-free tool profile.
- [ ] CA 6: Given a user in `platform` mode who is not entitled, when they try to select or use platform mode, then the backend returns `code = ai_runtime_platform_not_entitled` and Flutter does not present the failure as a missing OpenRouter key.
- [ ] CA 7: Given an entitled user selects `mode = platform`, when `PUT /api/settings/ai-runtime` succeeds, then the persisted effective mode becomes `platform` and the response payload matches the `GET /api/settings/ai-runtime` contract.
- [ ] CA 8: Given a user in `platform` mode with valid operator provider configuration, when they trigger a covered route without any user-managed AI credentials stored, then the route succeeds using operator-managed providers.
- [ ] CA 9: Given a user in `platform` mode with entitlement but a missing operator provider secret, when they trigger a route that needs that provider, then the backend returns a `503` runtime error with `code = ai_runtime_operator_provider_missing`.
- [ ] CA 10: Given a covered route touches memory and no safe runtime-aware Mem0 path is available, when the route runs, then generation continues with memory disabled and never falls back to `OPENROUTER_API_KEY`.
- [ ] CA 11: Given newsletter generation with request body `include_email_insights = false`, when no email backend is configured, then the route can still succeed if required AI providers are available.
- [ ] CA 12: Given newsletter generation with request body `include_email_insights = true`, when no email backend is configured, then the route fails with an explicit non-runtime configuration error rather than a hidden crew failure.
- [ ] CA 13: Given `dispatch-pipeline` with `target_format = newsletter`, when no email backend is configured, then the route can still succeed because angle-to-newsletter generation does not require inbox access.
- [ ] CA 14: Given two users with different runtime modes or different provider credentials, when they hit covered routes on the same backend process, then no provider client, LLM object, or tool profile is reused across those users.
- [ ] CA 15: Given persona draft `mode == blank_form`, when the user has no AI providers configured, then the request still succeeds exactly as the non-LLM exception path intends.
- [ ] CA 16: Given `dispatch-pipeline` runs successfully, when downstream crews finish, then exactly one canonical content record exists for the pipeline run.
- [ ] CA 17: Given Flutter receives a duplicate-content conflict from `dispatch-pipeline`, when it parses the response, then it is not treated as a missing-provider runtime error.
- [ ] CA 18: Given the Flutter newsletter screen calls `/api/newsletter/config/check`, when the dual-mode migration is in place, then it still receives `configured`, `ready`, `llm_configured`, `server_ready`, `checks`, and `instructions` with the semantics frozen by this spec.
- [ ] CA 19: Given `dispatch-pipeline` with `target_format = newsletter`, when the no-email profile is used, then inbox tools from `newsletter_agent.py` are not reachable in the agent tool list.
- [ ] CA 20: Given `/api/newsletter/config/check?include_email_insights=false`, when inbox dependencies are missing but AI providers are ready, then `server_ready` is `true`, `configured` is `llm_configured`, and `checks` still exposes the raw inbox dependency booleans.
- [ ] CA 21: Given newsletter generation requests email insights while no inbox backend is configured, when the backend rejects the request, then it returns `code = newsletter_email_backend_missing`, `kind = dependency`, and Flutter does not treat it as an AI runtime credential issue.
- [ ] CA 22: Given `PUT /api/settings/integrations/openrouter|exa|firecrawl` with a valid `secret`, when the write succeeds, then the response uses the generic provider status contract and `validationStatus` is `unknown` until explicit validation exists.
- [ ] CA 23: Given `AI_PLATFORM_MODE_ENABLED=true` and the current `user_id` is present in `AI_PLATFORM_MODE_ALLOWED_USER_IDS`, when the user selects `platform`, then the entitlement gate allows persistence and platform mode becomes selectable and usable.

## Test Strategy
- Backend unit tests:
  - runtime models
  - entitlement service
  - runtime resolver
  - provider tool profiles
  - memory runtime behavior
- Backend route tests:
  - persona draft
  - psychology narrative and angles
  - dispatch-pipeline by format
  - newsletter sync and async
  - research competitor analysis
- Test fixtures:
  - user A in `byok`
  - user B in `platform`
  - dummy global env vars present to prove covered routes ignore them
  - optional-provider test cases where `firecrawl` is intentionally absent
- Flutter tests:
  - API client runtime models
  - runtime error parsing
  - settings widget behavior for `byok` vs locked `platform`
- Manual smoke:
  - save/update/delete `openrouter`, `exa`, and `firecrawl`
  - switch modes
  - run persona draft, ritual, angles, article, newsletter, short, social, and research
  - verify missing-provider UI on each covered screen

## Risks
- The main technical risk is hidden provider usage inside crews and tools. Tool-profile injection is mandatory to make optional providers deterministic.
- Mem0 may still resist clean request-scoped configuration in some paths. If so, those paths must degrade to “memory disabled”, not env fallback.
- Platform mode can create false pricing expectations if exposed too broadly. The entitlement gate must default closed.
- Newsletter uses both AI providers and operator-managed email integrations; poor error separation would create confusing UX.
- Keeping temporary `/openrouter` aliases too long could preserve legacy assumptions in the app. The migration window should be explicit and short.

## Execution Notes
- Read these files first:
  - `contentflow_lab/api/services/user_key_store.py`
  - `contentflow_lab/api/services/user_llm_service.py`
  - `contentflow_lab/api/routers/settings_integrations.py`
  - `contentflow_lab/api/routers/psychology.py`
  - `contentflow_lab/api/routers/newsletter.py`
  - `contentflow_lab/api/routers/research.py`
  - `contentflow_lab/memory/memory_config.py`
  - `contentflow_app/lib/presentation/screens/settings/settings_screen.dart`
- Recommended execution order:
  1. Models
  2. Settings persistence
  3. Entitlement service
  4. Runtime resolver
  5. Settings API
  6. Tool-profile refactor
  7. Memory behavior
  8. Backend route migrations
  9. Flutter models and settings
  10. Flutter error handling
  11. Regression tests
- Validation commands:
  - `cd /home/claude/contentflow/contentflow_lab && pytest tests/test_ai_runtime_models.py tests/test_user_data_store_ai_runtime.py tests/test_ai_entitlement_service.py tests/test_ai_runtime_service.py tests/test_settings_ai_runtime_router.py tests/test_persona_draft_route.py tests/test_psychology_auth_jobs.py tests/test_dispatch_pipeline_runtime.py tests/test_newsletter_router.py tests/test_newsletter_memory_scoping.py tests/test_research_router.py`
  - `cd /home/claude/contentflow/contentflow_app && flutter test`
- Stop conditions:
  - stop if any covered route still reads provider env vars outside the centralized runtime resolver
  - stop if optional providers remain registered as broken tools instead of being removed from tool profiles
  - stop if any covered route still maps generic `409` to “OpenRouter missing”
  - stop if newsletter memory remains unscoped

## Open Questions
None.
