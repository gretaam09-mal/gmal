"""The input Provision hands to P-COST-ESTIMATE: the obligation's
deterministic details plus the company's own profile facts — nothing the
model has to look up itself. Built by services/memo.py from an
Analysis's items and services/analyses.py::build_facts.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileFact:
    """One company-profile fact, already labelled for the prompt — e.g.
    label="Annual revenue (GBP)", value="4200000"."""

    label: str
    value: str


@dataclass(frozen=True)
class CostEstimateContext:
    predicate_id: str
    obligation_summary: str
    rationale: str
    clause_refs: tuple[str, ...]
    clause_texts: tuple[str, ...]
    company_facts: tuple[ProfileFact, ...]
