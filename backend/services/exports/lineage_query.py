"""F8: assembles a LineageAppendix by walking from a memo version's
content back through predicates/obligations/clauses to their instrument
versions, cost templates, scenario-probability assumptions, and review
history — the DB-touching half of services/exports/lineage.py's pure
data shape.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (
    Analysis,
    Assumption,
    Clause,
    CostTemplate,
    EntityProfile,
    Instrument,
    InstrumentVersion,
    Memo,
    MemoVersion,
    Obligation,
    Predicate,
    Review,
    User,
)
from services.exports.lineage import (
    InstrumentLineageEntry,
    LineageAppendix,
    ProbabilitySourceEntry,
    ProfileLineageEntry,
    ReviewProvenanceEntry,
    TemplateLineageEntry,
)


def _predicate_ids(content: dict) -> list[uuid.UUID]:
    ids = [o["predicate_id"] for o in content.get("obligations", [])]
    ids += [e["predicate_id"] for e in content.get("excluded", [])]
    return [uuid.UUID(pid) for pid in ids]


def build_lineage_appendix(session: Session, memo_version: MemoVersion) -> LineageAppendix:
    memo = session.get(Memo, memo_version.memo_id)
    analysis = session.get(Analysis, memo.analysis_id) if memo.analysis_id else None

    instrument_versions: list[InstrumentLineageEntry] = []
    template_versions: list[TemplateLineageEntry] = []
    seen_instrument_versions: set[uuid.UUID] = set()
    seen_templates: set[uuid.UUID] = set()

    for predicate_id in _predicate_ids(memo_version.content):
        row = session.execute(
            select(Predicate, Obligation, InstrumentVersion, Instrument)
            .join(Obligation, Obligation.id == Predicate.obligation_id)
            .join(Clause, Clause.id == Obligation.clause_id)
            .join(InstrumentVersion, InstrumentVersion.id == Clause.instrument_version_id)
            .join(Instrument, Instrument.id == InstrumentVersion.instrument_id)
            .where(Predicate.id == predicate_id)
        ).first()
        if row is None:
            continue
        _predicate, obligation, instrument_version, instrument = row

        if instrument_version.id not in seen_instrument_versions:
            seen_instrument_versions.add(instrument_version.id)
            instrument_versions.append(
                InstrumentLineageEntry(
                    instrument_title=instrument.title,
                    version_label=instrument_version.version_label,
                    content_hash=instrument_version.content_hash,
                    valid_from=instrument_version.valid_from,
                )
            )

        template = session.execute(
            select(CostTemplate).where(
                CostTemplate.obligation_id == obligation.id, CostTemplate.valid_to.is_(None)
            )
        ).scalar_one_or_none()
        if template is not None and template.id not in seen_templates:
            seen_templates.add(template.id)
            template_versions.append(
                TemplateLineageEntry(
                    obligation_summary=obligation.summary,
                    template_name=template.name,
                    maturity_tier=template.maturity_tier,
                    source_basis=template.source_basis,
                    valid_from=template.valid_from,
                )
            )

    assumptions = session.execute(
        select(Assumption).where(Assumption.memo_version_id == memo_version.id)
    ).scalars()
    probability_sources = tuple(
        ProbabilitySourceEntry(key=a.key, source=a.source)
        for a in assumptions
        if a.key.startswith("scenario:")
    )

    reviews = session.execute(
        select(Review, User)
        .join(User, User.id == Review.reviewer_user_id)
        .where(Review.memo_version_id == memo_version.id)
        .order_by(Review.created_at)
    ).all()
    review_provenance = tuple(
        ReviewProvenanceEntry(
            reviewer_email=user.email,
            decision=review.decision.value,
            panel_firm=review.panel_firm,
            comment=review.comment,
            created_at=review.created_at,
        )
        for review, user in reviews
    )

    profile_version = None
    if analysis is not None:
        profile = session.get(EntityProfile, analysis.entity_profile_id)
        if profile is not None:
            profile_version = ProfileLineageEntry(
                version=profile.version,
                companies_house_number=profile.companies_house_number,
                recorded_at=profile.recorded_at,
            )

    return LineageAppendix(
        instrument_versions=tuple(instrument_versions),
        template_versions=tuple(template_versions),
        probability_sources=probability_sources,
        review_provenance=review_provenance,
        profile_version=profile_version,
    )
