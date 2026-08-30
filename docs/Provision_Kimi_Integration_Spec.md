# Provision — Kimi K3 Integration Spec

How to add Kimi K3 (Moonshot) as a second model provider without breaking Provision's trust rules.

## 0. Why this exists (read first)
Kimi K3 is cheap, has a 1M-token context, and is strong at long-document and coding work, useful for reading long public legislation and for development. But Moonshot's hosted API trains on submitted content with no documented opt-out, offers no enterprise DPA, and stores data in Singapore. That conflicts with Provision's rules (no client data in training; DPA with no-training terms on all LLM calls; EU data residency) and its promise of being safe for confidential deal material.
The rule this spec enforces in code: every AI call is tagged `public` or `confidential`, and a `confidential` call can never be sent to a provider that is not `confidential_ok`. Kimi's hosted API is `confidential_ok = false`. This is a gate with a test, not a guideline.

## 1. What Kimi is allowed to do
- Onboarding: extract obligations from public legislation — public — Kimi allowed (good fit: 1M context, low cost)
- Rule-drafting assistance over public legislation — public — Kimi allowed
- Horizon summarisation of public consultations — public — Kimi allowed
- Dev, testing, golden-set experimentation — public — Kimi allowed
- Memo prose composition over a client's target — confidential — NOT Kimi hosted (Claude, or self-hosted Kimi only)
- Indicative AI cost estimation over a specific target — confidential — NOT Kimi hosted
- Trajectory hypotheses over a specific company's footprint — confidential — NOT Kimi hosted
- Anything including a client's entity profile or deal inputs — confidential — NOT Kimi hosted
Self-hosted exception: an open-weight Kimi on Provision's own infrastructure counts as confidential_ok = true. Not needed to start.

## 2. The provider abstraction
Refactor services/ai so callers never talk to a vendor SDK directly; they call a router.
Provider interface: generate_structured(schema, messages, *, data_class), generate_text(messages, *, data_class), plus metadata: name, confidential_ok: bool, models, supports_structured: bool.
Register:
- claude — Anthropic, confidential_ok=true, structured output via existing Anthropic tool use (strict). Models: Sonnet (default), Opus (cost estimation).
- kimi — Moonshot, OpenAI-compatible, confidential_ok=false. Base URL https://api.moonshot.ai/v1, key MOONSHOT_API_KEY. Structured output via JSON-schema response_format. Model kimi-k3 (+ a cheaper kimi-k2.x tier for bulk).
- kimi_selfhosted — optional, later, confidential_ok=true, private base URL.
Output validation unchanged: parse and validate with the existing Pydantic schema; invalid output triggers schema-retry then provider fallback. The LLM never computes a number; Kimi does not touch arithmetic.

## 3. The data-sensitivity gate (the safety mechanism)
- Every call passes data_class: "public" | "confidential" as a required argument.
- If data_class == "confidential" and provider.confidential_ok is False, the router raises ConfidentialRoutingError before any network call.
- Task-to-provider policy lives in config:
AI_ROUTING = {
  "extraction":       {"primary": "kimi",   "fallback": "claude", "data_class": "public"},
  "rule_drafting":    {"primary": "kimi",   "fallback": "claude", "data_class": "public"},
  "horizon_summary":  {"primary": "kimi",   "fallback": "claude", "data_class": "public"},
  "memo_composition": {"primary": "claude", "fallback": "claude_fallback", "data_class": "confidential"},
  "cost_estimation":  {"primary": "claude", "fallback": "claude_fallback", "data_class": "confidential"},
  "trajectory_hypo":  {"primary": "claude", "fallback": "claude_fallback", "data_class": "confidential"},
}
- Tests (required): (a) a confidential call routed to kimi raises ConfidentialRoutingError; (b) a public call to kimi succeeds against a mocked client; (c) config that sets a confidential task's primary/fallback to a non-confidential_ok provider fails at load.

## 4. Fallback rules
- Public tasks: primary Kimi, fallback Claude (or reverse). Either fine, no confidential data.
- Confidential tasks: primary Claude, fallback must be another confidential_ok provider. Never Kimi hosted.
- Fallback triggers: transport error, timeout, or schema-validation failure after allowed retries.

## 5. Golden-eval gate (do not skip)
A new model is not trusted on a task until it passes that task's golden set. Before enabling Kimi as primary for extraction, run the extraction golden set against kimi-k3 vs Claude baseline (clause-citation accuracy, obligation recall/precision, schema validity). Only promote if it meets or beats threshold. Add Kimi runs to golden CI for the public tasks it serves. Keep dual-model cross-check on high-materiality obligations regardless of provider.

## 6. Config and secrets
MOONSHOT_API_KEY in the secret store (never in the repo). Feature flag KIMI_ENABLED (default off) to dark-launch. Log provider + model + data_class + task to metrics_events on every call.

## 7. Scope guard
Change lives in services/ai, config, and tests. Does not touch engine/. Trust-sensitive, so request manual review even though it is a non-engine PR. Does not change prompt content, only routing and validation. One feature per branch; write the gate tests first.
