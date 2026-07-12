"""F8's lineage appendix: everything a reader needs to trace a memo's
figures back to their sources — instrument versions, the profile version
analysed, cost-template versions, scenario-probability sources, and the
review that approved it. The dataclasses here are the pure data shape;
build_lineage_appendix (services/exports/lineage_query.py) is the thin
DB-touching half that assembles them.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class InstrumentLineageEntry:
    instrument_title: str
    version_label: str
    content_hash: str
    valid_from: datetime


@dataclass(frozen=True)
class TemplateLineageEntry:
    obligation_summary: str
    template_name: str
    maturity_tier: str
    source_basis: str
    valid_from: datetime


@dataclass(frozen=True)
class ProbabilitySourceEntry:
    key: str
    source: str


@dataclass(frozen=True)
class ReviewProvenanceEntry:
    reviewer_email: str
    decision: str
    panel_firm: str | None
    comment: str | None
    created_at: datetime


@dataclass(frozen=True)
class ProfileLineageEntry:
    version: int
    companies_house_number: str | None
    recorded_at: datetime


@dataclass(frozen=True)
class LineageAppendix:
    instrument_versions: tuple[InstrumentLineageEntry, ...]
    template_versions: tuple[TemplateLineageEntry, ...]
    probability_sources: tuple[ProbabilitySourceEntry, ...]
    review_provenance: tuple[ReviewProvenanceEntry, ...]
    profile_version: ProfileLineageEntry | None
