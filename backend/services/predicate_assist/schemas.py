"""Pydantic validation for P-PREDICATE-ASSIST's output — see
ai/prompts/P-PREDICATE-ASSIST.v1.md.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from engine.predicates.dsl import InvalidExpressionError, validate_expression


class DraftedPredicate(BaseModel):
    predicate_key: str = Field(min_length=1, max_length=100)
    expression: dict
    explanation: str = Field(min_length=1, max_length=500)

    @field_validator("expression")
    @classmethod
    def _must_be_valid_dsl(cls, value: dict) -> dict:
        try:
            validate_expression(value)
        except InvalidExpressionError as exc:
            raise ValueError(str(exc)) from exc
        return value
