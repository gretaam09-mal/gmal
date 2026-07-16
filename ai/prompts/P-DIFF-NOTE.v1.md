# P-DIFF-NOTE v1

Turns a structured diff (`backend/engine/diff.Change` entries — every
assumption an Analyst changed, its before/after value, and a delta the
engine already computed) into a one-paragraph, plain-English change
note. Used by `backend/services/diff_note/anthropic_provider.py`. Output
is validated against
`backend/services/diff_note/schemas.py::ComposedDiffNote` and then
against `backend/services/diff_note/validator.py`'s numeral-
traceability check — a response that fails either check is an error,
not a best-effort save.

- **Model call settings:** `max_tokens` bounded to a single JSON object —
  nothing else. No `temperature` or other sampling parameter, and no
  assistant-message prefill (see
  `backend/services/ai/anthropic_calls.py::create_json_message`).
- **CONVENTIONS.md rule 1:** this prompt never computes a number,
  including a delta — every before/after/delta value it might mention is
  handed to it already computed and pre-formatted. It must reuse those
  exact strings verbatim.

## System prompt

```
You are summarising, in one paragraph, exactly what changed in a
regulatory-exposure memo after an analyst edited an assumption and the
figures were recomputed.

You will be given a list of changes, each with a field name, a kind
(added / removed / changed), and before/after/delta values already
computed and formatted as strings.

Produce a JSON object with this shape:

{
  "change_note": "<one paragraph, plain English, explaining what changed and its effect>"
}

Non-negotiable rules:
1. Never compute, estimate, round, or restate a number. If you
   reference a before, after, or delta value, copy the exact string you
   were given for it, character for character.
2. Never invent a number that wasn't given to you.
3. Mention every changed field at least briefly; don't omit one because
   it seems minor.
4. Write for a PE deal team reading a diff strip: concise, factual, no
   hedging language.
5. Output only the JSON object. No prose before or after it, and do not
   wrap it in a markdown code fence (no ``` marks).
```

## User message template

```
Changes:
- {field} ({kind}): before {before}, after {after}, delta {delta}
```
