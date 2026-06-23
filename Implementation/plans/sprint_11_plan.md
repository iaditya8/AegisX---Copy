# Sprint 11 — Implementation Plan

> **Paste your implementation plan for Sprint 11 below this line.**
> Delete this placeholder text when adding your content.

Implementation Plan - Sprint 11: AI Security Copilot Framework

Transform AegisX from a reporting platform into an AI-assisted exposure management platform by introducing an advisory AI Security Copilot layer.

User Review Required

[!IMPORTANT]The AI layer acts strictly as an advisory system and operates on read-only inputs. It cannot perform any actions, discover assets, scan targets, or change risk/criticality scores.

[!IMPORTANT]The AI layer must never directly query database tables. The Context Builder dynamically compiles context data by invoking existing services and snapshots/reports rather than querying the database tables with custom SQL or select joins.

Proposed Changes

AI Service Layer & Safety Guardrails

[NEW] copilot_response_schema.py

Defines First-Class Contracts for AI Responses to ensure compatibility against prompt changes, model upgrades, and future automated workflows.

Defines Pydantic models:

AssetExplanationSchema (summary, risk_analysis, priority_reasons, etc.)

FindingExplanationSchema (summary, impact, priority, investigation_guidance, etc.)

ExecutiveSummarySchema (executive_summary, top_risks, notable_changes, etc.)

[NEW] ai_guardrails.py

Implements AIGuardrails to filter context objects before they are passed to the prompt builder.

Methods:

sanitize_context(context: dict) -> dict: Recursively scans context structures to redact credentials, API keys, tokens, session cookies, passwords, authorization headers, and raw requests/responses containing secrets.

Exposes validate_asset_context(...), validate_finding_context(...), and validate_executive_context(...).

[NEW] ai_context_builder.py

Aggregates data from existing domain services (AssetReportService, ExecutiveReportService, RiskReportService, DashboardTrendService).

Introduces CONTEXT_VERSION = "1.0".

Implements:

build_asset_context(db, asset_id)

build_finding_context(db, finding_id)

build_executive_context(db)

Outputs a standardized structure containing versioning:

{
    "context_version": "1.0",
    "asset": {},
    "risk": {},
    "findings": [],
    "correlation": {}
}

[NEW] ai_prompt_builder.py

Converts sanitized context objects into deterministic prompts.

Strictly instructs the LLM to output valid JSON only, without markdown wrappers, code blocks, or extra explanatory text.

Implements:

build_asset_prompt(context)

build_finding_prompt(context)

build_executive_prompt(context)

[NEW] ai_provider.py

Defines abstract base interface AIProvider with:

async def generate(self, prompt: str) -> str

def get_name(self) -> str

def get_version(self) -> str

[NEW] openai_provider.py

Implements OpenAIProvider consuming OPENAI_API_KEY from the environment.

Returns get_name() -> "openai" and get_version() -> "gpt-4o-mini".

Leverages httpx.AsyncClient with timeouts, transient error retry loops, and structured logging.

[NEW] ai_provider_registry.py

Implements AIProviderRegistry to resolve the active provider.

Methods:

get_provider() -> AIProvider: Reads AI_PROVIDER environment variable (defaults to openai) and returns the appropriate provider instance.

[NEW] ai_response_validator.py

Implements AIResponseValidator to enforce schema boundaries before returning. Creates immutable contracts between the Prompt Builder, Provider, Validator, and API Layer.

Methods:

validate_asset_response(response_str: str) -> Dict[str, Any]: Parses the response string as JSON and validates it against AssetExplanationSchema.

validate_finding_response(response_str: str) -> Dict[str, Any]: Parses and validates against FindingExplanationSchema.

validate_executive_response(response_str: str) -> Dict[str, Any]: Parses and validates against ExecutiveSummarySchema.

Raises ValueError if validation fails or structure is malformed. No heuristic repairs or retries.

[NEW] ai_rate_limit_service.py

Implements AIRateLimitService for simple, in-memory usage tracking.

Hour-window rate limits:

admin: 1000 requests per hour

operator: 250 requests per hour

Exposes check_rate_limit(user_id: uuid.UUID, role: str) -> bool.

AI Copilot & Cache Services

[NEW] ai_cache_service.py

In-memory caching of explanation payloads using structured keys containing the context version:

(asset_id, context_version, prompt_hash)

(finding_id, context_version, prompt_hash)

("executive", context_version, prompt_hash)

Implements TTL validation (1 hour) and invalidation functions (invalidate_for_asset(asset_id)).

[NEW] ai_audit_service.py

Computes SHA-256 hashes of prompts/responses to record requests inside the existing audit_logs table (using metadata_json).

Saves provider metadata versioning dynamically:

{
    "request_type": "...",
    "asset_id": "...",
    "finding_id": "...",
    "timestamp": "...",
    "prompt_hash": "...",
    "response_hash": "...",
    "provider": provider_name,
    "provider_version": provider_version
}

Never stores raw inputs/outputs.

[NEW] asset_copilot_service.py

Implements explain_asset(db, asset_id) coordinating context builder, prompt builder, cache service, and provider.

Failure Fallback Contract:

If provider throws timeout/connection errors, is rate-limited, or response fails Pydantic schema validation:Returns a structured dictionary indicating failure gracefully:

{
  "success": false,
  "source": "fallback",
  "message": "AI explanation unavailable",
  "generated_at": "...",
  "summary": "",
  "risk_analysis": "",
  "priority_reasons": []
}

Never raises HTTP 500 or crashes scanning/API layers.

[NEW] finding_copilot_service.py

Implements explain_finding(db, finding_id) coordinating prompt assembly, AI execution, cache, and auditing.

Failure Fallback Contract:

Returns fallback JSON structure in case of any provider/validation failures:

{
  "success": false,
  "source": "fallback",
  "message": "AI explanation unavailable",
  "generated_at": "...",
  "summary": "",
  "impact": "",
  "priority": "",
  "investigation_guidance": ""
}

[NEW] executive_copilot_service.py

Implements generate_executive_summary(db) coordinating executive summaries.

Failure Fallback Contract:

Returns fallback JSON structure:

{
  "success": false,
  "source": "fallback",
  "message": "AI explanation unavailable",
  "generated_at": "...",
  "executive_summary": "",
  "top_risks": [],
  "notable_changes": []
}

Workflow & Invalidation Integrations

[MODIFY] report_cache_service.py

Updates invalidate_for_asset and invalidate_all to cascade invalidations to AICacheService.

[MODIFY] worker.py

Hook cache invalidation into the Celery task completed steps and cache refreshes:

Calls AICacheService.invalidate_for_asset(asset.id) after step completions.

Calls AICacheService.invalidate_for_asset("executive") after report cache refreshes.

Presentation / API Layer

[NEW] copilot.py

Pydantic models for request/response bodies incorporating metadata attributes for success, source, and message:

AssetExplanationResponse

FindingExplanationResponse

ExecutiveSummaryResponse

[NEW] copilot.py

Exposes versioned API routes with authentication, ownership, and strict RBAC checks (admin, operator allowed; reader blocked):

GET /api/v1/copilot/assets/{id}

GET /api/v1/copilot/findings/{id}

GET /api/v1/copilot/executive

Enforces rate limits via AIRateLimitService. Returns HTTP 429 Too Many Requests if limits are exceeded.

Emits events copilot.requested, copilot.generated, and copilot.cached inside the database.

[MODIFY] main.py

Registers the new copilot_router under /api/v1.

Verification and Tests

[NEW] test_copilot.py

Implements all requested scenario test assertions covering:

Provider Registry: test_provider_registry_returns_openai_provider

Context Version: test_context_version_present

Response Validation: test_invalid_ai_response_rejected

Rate Limiting: test_rate_limit_enforced

Cache Version Isolation: test_cache_version_isolation

Safety Redaction: test_safety_guardrails_redact_secrets

Context & prompt builders

Caching (retrieval, TTL expiry, invalidation)

Copilot services (asset, finding, executive summary)

Security checks (missing key, timeout handlers, retry loop recoveries)

API layers (endpoints, RBAC rules)

Audit logging & hashes

Empty database and missing model stability

Verification Plan

Automated Tests

Run copilot tests specifically:

.venv\Scripts\pytest backend/tests/integration/test_copilot.py

Run the full test suite:

.venv\Scripts\pytest

Run formatting and check style compliance:

.venv\Scripts\ruff check backend/
.venv\Scripts\black --check backend/