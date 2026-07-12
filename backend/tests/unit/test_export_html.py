from datetime import UTC, datetime

from services.exports.html import render_memo_html
from services.exports.lineage import (
    InstrumentLineageEntry,
    LineageAppendix,
    ProbabilitySourceEntry,
    ProfileLineageEntry,
    ReviewProvenanceEntry,
    TemplateLineageEntry,
)

_CONTENT = {
    "headline": {"low": "20000.00", "likely": "25000.00", "high": "32500.00", "currency": "GBP"},
    "confidence_grade": "B",
    "confidence_score": "78.5",
    "headline_summary": "This deal carries a bounded, quantified regulatory exposure.",
    "obligations": [
        {
            "predicate_id": "pred-1",
            "obligation_summary": "Appoint a data protection officer.",
            "clause_refs": ["s.1"],
            "rationale": "Binds: processes personal data.",
            "impact_low": "20000.00",
            "impact_likely": "25000.00",
            "impact_high": "32500.00",
            "currency": "GBP",
            "phased_schedule": [{"period": "2027-01", "amount": "25000.00"}],
            "present_value": "24000.00",
            "what_it_requires": "Appoint a data protection officer.",
            "why_it_applies": "The target processes personal data at scale.",
        }
    ],
    "excluded": [
        {
            "predicate_id": "pred-2",
            "obligation_summary": "Client money segregation.",
            "outcome": "does_not_bind",
            "rationale": "Does not bind: does not hold client money.",
        }
    ],
    "excluded_summary": "One obligation was excluded — see below.",
}

_ASSUMPTIONS = [
    {
        "key": "discount_rate_pct",
        "value": {"value": "5"},
        "source": "analysis_setting",
        "note": None,
    },
]

_LINEAGE = LineageAppendix(
    instrument_versions=(
        InstrumentLineageEntry(
            instrument_title="Test Data Protection Act",
            version_label="v1",
            content_hash="abc123",
            valid_from=datetime(2027, 1, 1, tzinfo=UTC),
        ),
    ),
    template_versions=(
        TemplateLineageEntry(
            obligation_summary="Appoint a data protection officer.",
            template_name="DPO cost",
            maturity_tier="rough",
            source_basis="expert estimate",
            valid_from=datetime(2027, 1, 1, tzinfo=UTC),
        ),
    ),
    probability_sources=(
        ProbabilitySourceEntry(key="scenario:pred-1:as_drafted", source="base_rate_table"),
    ),
    review_provenance=(
        ReviewProvenanceEntry(
            reviewer_email="reviewer@example.com",
            decision="approved",
            panel_firm="Outside Counsel LLP",
            comment=None,
            created_at=datetime(2027, 1, 5, tzinfo=UTC),
        ),
    ),
    profile_version=ProfileLineageEntry(
        version=2, companies_house_number="12345678", recorded_at=datetime(2027, 1, 1, tzinfo=UTC)
    ),
)


def _render(*, title="Project Falcon", content=None, assumptions=None):
    return render_memo_html(
        memo_title=title,
        content=content if content is not None else _CONTENT,
        assumptions=assumptions if assumptions is not None else _ASSUMPTIONS,
        lineage=_LINEAGE,
    )


def test_render_memo_html_includes_headline_and_confidence():
    html = _render(title="Project Falcon — Impact Memo")
    assert "Project Falcon" in html
    assert "25000.00" in html
    assert "Confidence grade: B" in html or ">B<" in html


def test_render_memo_html_includes_obligation_clause_refs():
    html = _render()
    assert "Appoint a data protection officer." in html
    assert "s.1" in html


def test_render_memo_html_includes_excluded_section():
    html = _render()
    assert "Client money segregation." in html


def test_render_memo_html_includes_assumption_register():
    html = _render()
    assert "discount_rate_pct" in html
    assert "analysis_setting" in html


def test_render_memo_html_includes_lineage_appendix():
    html = _render()
    assert "Test Data Protection Act" in html
    assert "abc123" in html
    assert "DPO cost" in html
    assert "base_rate_table" in html
    assert "reviewer@example.com" in html
    assert "Outside Counsel LLP" in html
    assert "12345678" in html


def test_render_memo_html_is_valid_enough_html_and_has_print_styles():
    html = _render()
    assert html.strip().startswith("<!doctype html>") or html.strip().startswith("<html")
    assert "@media print" in html or "@page" in html


def test_render_memo_html_is_deterministic():
    assert _render() == _render()


def test_render_memo_html_escapes_untrusted_text():
    """Obligation summaries etc. ultimately trace back to extracted
    clause text — never trust it not to contain HTML-significant
    characters when embedding into the document."""
    content = {**_CONTENT, "headline_summary": "<script>alert(1)</script>"}
    html = _render(content=content)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
