#!/usr/bin/env python3
"""Populates 3-4 SAMPLE/fixture instruments end-to-end, to prove the F3
pipeline works: ingest -> clause-segment -> extract -> expert-review
(auto-approved here, standing in for a human click) -> draft a predicate
-> approve it -> attach a cost template -> (if run twice) the onboarding
metric only fires once per instrument.

These are deliberately fictional sample regulations, not real FCA
content — that is expert work for later (see F3's spec). Uses the same
fixture providers tests use (no live model call — see
services/extraction/fixture_provider.py) because this script's job is to
prove the pipeline's plumbing, not to demonstrate real extraction
quality.

Usage: poetry run python -m scripts.populate_sample_instruments
"""

from __future__ import annotations

from sqlalchemy import select

from db.models import Instrument, User
from db.session import raw_session
from services.extraction import ExtractedObligation, FixtureExtractionProvider
from services.instrument_onboarding import (
    approve_obligation,
    approve_predicate,
    attach_cost_template,
    create_predicate,
    extract_obligation,
    ingest_instrument,
    list_clauses,
)


def _staff_user(session):
    user = session.execute(
        select(User).where(User.email == "onboarding-sample@provision.invalid")
    ).scalar_one_or_none()
    if user is None:
        user = User(
            clerk_user_id="clerk_sample_onboarding_staff",
            email="onboarding-sample@provision.invalid",
            name="Sample Onboarding Script",
            is_staff=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


_SAMPLE_INSTRUMENTS = [
    {
        "title": "Sample Data Protection (Fictional) Act 2026",
        "jurisdiction": "UK",
        "kind": "Act",
        "citation": "Sample DP Act 2026",
        "version_label": "v1",
        "raw_text": (
            "1. A firm that processes personal data at scale must appoint a "
            "data protection officer within 30 days of exceeding the threshold.\n\n"
            "2. The data protection officer must report material data breaches "
            "to the regulator within 72 hours of discovery."
        ),
        "obligation": {
            "clause_ref": "s.1",
            "summary": "Appoint a data protection officer if processing personal data at scale.",
            "obligation_type": "appointment",
            "who": "firms processing personal data at scale",
            "what": "appoint a data protection officer",
            "when": "within 30 days of exceeding the threshold",
            "threshold": "processes personal data at scale",
            "enforcer": "the Information Commissioner's Office (sample)",
            "confidence": 90,
        },
        "predicate_key": "processes_personal_data",
        "expression": {"field": "footprint.processes_personal_data", "equals": True},
        "cost_template": {
            "name": "DPO appointment cost — rough estimate",
            "drivers": [{"key": "scale.employee_count", "label": "Employee count"}],
            "formula": {"base": 5000, "terms": [{"driver": "scale.employee_count", "rate": 40}]},
            "currency": "GBP",
            "source_basis": "expert estimate",
            "maturity_tier": "rough",
        },
    },
    {
        "title": "Sample Client Money (Fictional) Rules 2026",
        "jurisdiction": "UK",
        "kind": "Regulation",
        "citation": "Sample CASS 2026",
        "version_label": "v1",
        "raw_text": (
            "1. A firm that holds client money must keep it segregated from "
            "the firm's own money in a designated client account."
        ),
        "obligation": {
            "clause_ref": "s.1",
            "summary": "Segregate client money from the firm's own money.",
            "obligation_type": "record-keeping",
            "who": "firms holding client money",
            "what": "segregate client money in a designated account",
            "when": "not specified in this clause",
            "threshold": "holds client money",
            "enforcer": "the regulator (sample)",
            "confidence": 85,
        },
        "predicate_key": "holds_client_money",
        "expression": {"field": "footprint.holds_client_money", "equals": True},
        "cost_template": {
            "name": "Client money segregation cost — benchmarked",
            "drivers": [
                {"key": "cost_sketch.compliance_headcount", "label": "Compliance headcount"}
            ],
            "formula": {
                "base": 15000,
                "terms": [{"driver": "cost_sketch.compliance_headcount", "rate": 8000}],
            },
            "currency": "GBP",
            "source_basis": "vendor quote",
            "maturity_tier": "benchmarked",
        },
    },
    {
        "title": "Sample Hazardous Materials (Fictional) Regulations 2026",
        "jurisdiction": "UK",
        "kind": "Regulation",
        "citation": "Sample Hazmat Regs 2026",
        "version_label": "v1",
        "raw_text": (
            "1. A site that handles hazardous materials must file an annual "
            "disclosure with the environmental regulator."
        ),
        "obligation": {
            "clause_ref": "s.1",
            "summary": "File an annual disclosure if the site handles hazardous materials.",
            "obligation_type": "disclosure",
            "who": "sites handling hazardous materials",
            "what": "file an annual disclosure",
            "when": "annually",
            "threshold": "handles hazardous materials",
            "enforcer": "the Environment Agency (sample)",
            "confidence": 82,
        },
        "predicate_key": "handles_hazardous_materials",
        "expression": {"field": "footprint.handles_hazardous_materials", "equals": True},
        "cost_template": {
            "name": "Annual hazmat disclosure cost — rough estimate",
            "drivers": [],
            "formula": {"base": 3000},
            "currency": "GBP",
            "source_basis": "expert estimate",
            "maturity_tier": "rough",
        },
    },
]


def populate() -> None:
    with raw_session() as session:
        staff = _staff_user(session)

        for spec in _SAMPLE_INSTRUMENTS:
            existing = session.execute(
                select(Instrument).where(Instrument.title == spec["title"])
            ).scalar_one_or_none()
            if existing is not None:
                print(f"Skipping (already onboarded): {spec['title']}")
                continue

            version = ingest_instrument(
                session,
                title=spec["title"],
                jurisdiction=spec["jurisdiction"],
                kind=spec["kind"],
                citation=spec["citation"],
                version_label=spec["version_label"],
                source_url=None,
                raw_text=spec["raw_text"],
            )
            session.commit()

            clauses = {c.clause_ref: c for c in list_clauses(session, version.id)}
            clause = clauses[spec["obligation"]["clause_ref"]]

            o = spec["obligation"]
            extracted = ExtractedObligation.model_validate(
                {
                    "summary": o["summary"],
                    "obligation_type": o["obligation_type"],
                    "who": {
                        "value": o["who"],
                        "clause_ref": clause.clause_ref,
                        "confidence": o["confidence"],
                    },
                    "what": {
                        "value": o["what"],
                        "clause_ref": clause.clause_ref,
                        "confidence": o["confidence"],
                    },
                    "when": {"value": o["when"], "clause_ref": clause.clause_ref, "confidence": 40},
                    "threshold": {
                        "value": o["threshold"],
                        "clause_ref": clause.clause_ref,
                        "confidence": o["confidence"],
                    },
                    "enforcer": {
                        "value": o["enforcer"],
                        "clause_ref": clause.clause_ref,
                        "confidence": 60,
                    },
                    "confidence": o["confidence"],
                }
            )
            provider = FixtureExtractionProvider({clause.clause_ref: extracted})
            obligation = extract_obligation(
                session, clause=clause, instrument_title=spec["title"], provider=provider
            )
            session.commit()

            # Standing in for a human clicking "approve" in the admin UI.
            approve_obligation(session, obligation=obligation, approved_by_user_id=staff.id)
            session.commit()

            predicate = create_predicate(
                session,
                obligation=obligation,
                predicate_key=spec["predicate_key"],
                expression=spec["expression"],
            )
            approve_predicate(session, predicate=predicate, approved_by_user_id=staff.id)
            session.commit()

            attach_cost_template(session, obligation=obligation, **spec["cost_template"])
            session.commit()

            print(f"Onboarded: {spec['title']} (instrument {version.instrument_id})")


if __name__ == "__main__":
    populate()
