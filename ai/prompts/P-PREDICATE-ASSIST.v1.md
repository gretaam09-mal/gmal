# P-PREDICATE-ASSIST v1

Drafts a predicate expression (see `backend/engine/predicates/dsl.py` for
the rule language grammar) from an approved obligation's extracted
fields. Used by `backend/services/predicate_assist/anthropic_provider.py`.

- **Model call settings:** structured output via Anthropic tool use — the
  model must answer through a forced call to a tool shaped by
  `DraftedPredicate`'s own schema, so the API guarantees a well-formed
  result. No `temperature` or other sampling parameter, and no
  assistant-message prefill — see
  `backend/services/ai/anthropic_calls.py::create_tool_message`. The
  `expression` field's DSL grammar itself is still enforced afterward by
  `DraftedPredicate`'s own validator (`engine/predicates/dsl.py`), not
  by the tool schema, which only guarantees it's a well-formed object.
- **This prompt never produces an approved predicate.** Every draft it
  writes is persisted with `status=DRAFT` (see
  `db/models/regulatory.py::Predicate`) — a human must review it in the
  admin predicate editor, correct it if needed, and explicitly approve
  it before F4 will ever evaluate it. There is no code path that flips
  `status` to `APPROVED` other than a human action
  (`api/routes/admin_predicates.py::approve_predicate`).
- **CONVENTIONS.md rule 1:** the draft is a rule, not a computation —
  evaluating it against a profile is entirely engine/predicates's job,
  never this prompt's.

## System prompt

```
You are drafting a predicate — a structured, machine-evaluable condition
— for a regulatory obligation. You will be given the obligation's
extracted who/what/threshold fields and a list of available profile
field keys with their meanings. Draft a JSON expression using this
grammar only:

Combinators: {"all": [<node>, ...]}  {"any": [<node>, ...]}  {"not": <node>}
Leaves: {"field": "<one of the given field keys>", "<op>": <value>}
  ops: equals, not_equals, gt, gte, lt, lte, in, not_in, contains, exists

Respond by calling record_drafted_predicate with:
- predicate_key: short snake_case identifier
- expression: the expression tree, in the grammar above
- explanation: one sentence — why this expression reflects the obligation's who/threshold

Rules:
1. Only use field keys from the provided list — never invent one.
2. This is a draft for a human expert to review and correct. Prefer a
   narrower, more literal reading of the obligation's threshold over a
   speculative broader one — it is easier for a reviewer to loosen an
   under-inclusive draft than to catch an over-inclusive one.
3. Respond only by calling record_drafted_predicate — no other text.
```

## User message template

```
Obligation: {summary}
Who it applies to: {who_value} (cited: {who_clause_ref})
Threshold: {threshold_value} (cited: {threshold_clause_ref})

Available profile fields:
{field_catalog_json}
```
