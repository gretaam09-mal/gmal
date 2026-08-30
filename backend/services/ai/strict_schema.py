"""Shared by every provider that supports strict, schema-enforced
structured output (services/ai/claude_provider.py, services/ai/
kimi_provider.py — both vendors' strict JSON-schema modes share the same
constraints: no numeric/length/pattern keywords, additionalProperties:
false on every object, not just the top one). See
services/ai/anthropic_calls.py's module docstring for the fuller story of
why plain (non-strict) tool/function-calling only *guides* a model toward
a schema rather than guaranteeing it.
"""
from __future__ import annotations

from typing import Any

# JSON Schema keywords Pydantic's model_json_schema() emits that strict
# structured-output modes don't support (numeric/length/pattern
# constraints). Stripping them here doesn't weaken validation: every
# caller still runs the model's own Model.model_validate(data) on the
# result, which enforces min_length, ge/le, and any @model_validator
# ordering checks exactly as before. This only relaxes what the API
# itself is asked to guarantee syntactically.
STRICT_UNSUPPORTED_KEYWORDS = frozenset(
    {
        "minLength",
        "maxLength",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minItems",
        "maxItems",
        "pattern",
        "uniqueItems",
    }
)


def prepare_strict_schema(schema: Any) -> Any:
    """Recursively makes a Model.model_json_schema() output strict-mode
    safe: strips unsupported constraint keywords, and sets
    additionalProperties: false on every object schema (required at every
    level, not just the top one — a nested object without it is exactly
    how a malformed/wrapped response can slip past a schema that only
    constrained the outer shape)."""
    if isinstance(schema, list):
        return [prepare_strict_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema

    schema = {
        key: value for key, value in schema.items() if key not in STRICT_UNSUPPORTED_KEYWORDS
    }

    if schema.get("type") == "object":
        schema["additionalProperties"] = False

    for key in ("properties", "$defs"):
        if key in schema:
            schema[key] = {
                inner_key: prepare_strict_schema(value) for inner_key, value in schema[key].items()
            }

    for key in ("items", "anyOf", "allOf", "oneOf"):
        if key in schema:
            schema[key] = prepare_strict_schema(schema[key])

    return schema
