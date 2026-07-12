"""F8: the print-styled HTML the memo, assumption register, and lineage
appendix render into — the single source both the PDF exporter (via
headless Chromium's page.set_content()+page.pdf()) and a human previewing
in a browser read from, so the two always match exactly.

Pure — no I/O, no DB access, takes only already-fetched data — so it's
fully unit-testable without a database.
"""
from __future__ import annotations

import html as html_lib
from typing import Any

from services.exports.lineage import LineageAppendix

_STYLE = """
<style>
  body { font-family: Georgia, 'Times New Roman', serif; color: #1a1a1a; margin: 2rem; }
  h1 { font-size: 1.5rem; }
  h2 { font-size: 1.1rem; border-bottom: 1px solid #ccc; padding-bottom: 0.25rem; }
  h3 { font-size: 0.95rem; }
  .confidence { font-family: Helvetica, Arial, sans-serif; font-size: 0.85rem; color: #555; }
  section { margin-bottom: 1.5rem; page-break-inside: avoid; }
  article.obligation { margin-bottom: 1rem; page-break-inside: avoid; }
  table { border-collapse: collapse; width: 100%; font-size: 0.85rem; }
  th, td { border: 1px solid #ddd; padding: 0.25rem 0.5rem; text-align: left; }
  .clauses { font-size: 0.8rem; color: #555; }
  @media print {
    body { margin: 1cm; }
    section { page-break-inside: avoid; }
  }
  @page { margin: 2cm; }
</style>
"""


def _esc(value: Any) -> str:
    return html_lib.escape(str(value))


def _obligation_html(obligation: dict) -> str:
    parts = [
        '<article class="obligation">',
        f"<h3>{_esc(obligation['obligation_summary'])}</h3>",
        f"<p>{_esc(obligation['what_it_requires'])}</p>",
        f"<p>{_esc(obligation['why_it_applies'])}</p>",
        '<p class="clauses">Clauses: '
        + ", ".join(_esc(ref) for ref in obligation["clause_refs"])
        + "</p>",
        f"<p>Cost: best {_esc(obligation['impact_low'])}, "
        f"likely {_esc(obligation['impact_likely'])}, "
        f"worst {_esc(obligation['impact_high'])} {_esc(obligation['currency'])}</p>",
        "<table><tr><th>Period</th><th>Amount</th></tr>",
    ]
    for entry in obligation["phased_schedule"]:
        parts.append(f"<tr><td>{_esc(entry['period'])}</td><td>{_esc(entry['amount'])}</td></tr>")
    parts.append("</table>")
    parts.append(f"<p>Present value: {_esc(obligation['present_value'])}</p>")
    parts.append("</article>")
    return "".join(parts)


def _lineage_html(lineage: LineageAppendix) -> str:
    parts = ['<section class="lineage">', "<h2>Lineage appendix</h2>"]

    parts.append("<h3>Instrument versions</h3><ul>")
    for entry in lineage.instrument_versions:
        parts.append(
            f"<li>{_esc(entry.instrument_title)} {_esc(entry.version_label)} "
            f"(hash {_esc(entry.content_hash)}, "
            f"effective {_esc(entry.valid_from.isoformat())})</li>"
        )
    parts.append("</ul>")

    parts.append("<h3>Cost template versions</h3><ul>")
    for entry in lineage.template_versions:
        parts.append(
            f"<li>{_esc(entry.obligation_summary)}: {_esc(entry.template_name)} "
            f"({_esc(entry.maturity_tier)}, {_esc(entry.source_basis)}, "
            f"effective {_esc(entry.valid_from.isoformat())})</li>"
        )
    parts.append("</ul>")

    parts.append("<h3>Scenario probability sources</h3><ul>")
    for entry in lineage.probability_sources:
        parts.append(f"<li>{_esc(entry.key)}: {_esc(entry.source)}</li>")
    parts.append("</ul>")

    parts.append("<h3>Review provenance</h3><ul>")
    for entry in lineage.review_provenance:
        firm = f" ({_esc(entry.panel_firm)})" if entry.panel_firm else ""
        parts.append(
            f"<li>{_esc(entry.reviewer_email)}{firm} — {_esc(entry.decision)} "
            f"at {_esc(entry.created_at.isoformat())}</li>"
        )
    parts.append("</ul>")

    if lineage.profile_version is not None:
        profile = lineage.profile_version
        ch_number = (
            f", Companies House {_esc(profile.companies_house_number)}"
            if profile.companies_house_number
            else ""
        )
        parts.append(
            f"<p>Entity profile version {_esc(profile.version)}{ch_number}, "
            f"recorded {_esc(profile.recorded_at.isoformat())}</p>"
        )

    parts.append("</section>")
    return "".join(parts)


def render_memo_html(
    *, memo_title: str, content: dict, assumptions: list[dict], lineage: LineageAppendix
) -> str:
    headline = content["headline"]
    parts: list[str] = [
        "<!doctype html>",
        '<html><head><meta charset="utf-8">',
        f"<title>{_esc(memo_title)}</title>",
        _STYLE,
        "</head><body>",
        f"<h1>{_esc(memo_title)}</h1>",
        f'<p class="confidence">Confidence grade: {_esc(content["confidence_grade"])} '
        f"({_esc(content['confidence_score'])})</p>",
        '<section class="headline">',
        "<h2>Headline exposure</h2>",
        f"<p>Best {_esc(headline['low'])} {_esc(headline['currency'])} &middot; "
        f"Likely {_esc(headline['likely'])} {_esc(headline['currency'])} &middot; "
        f"Worst {_esc(headline['high'])} {_esc(headline['currency'])}</p>",
        f"<p>{_esc(content['headline_summary'])}</p>",
        "</section>",
        '<section class="obligations">',
        "<h2>Obligations</h2>",
    ]
    parts.extend(_obligation_html(o) for o in content["obligations"])
    parts.append("</section>")

    parts.append('<section class="excluded">')
    parts.append("<h2>Excluded obligations</h2>")
    parts.append(f"<p>{_esc(content['excluded_summary'])}</p>")
    for item in content["excluded"]:
        parts.append(
            f"<p><strong>{_esc(item['obligation_summary'])}</strong> — "
            f"{_esc(item['rationale'])}</p>"
        )
    parts.append("</section>")

    parts.append('<section class="assumptions">')
    parts.append("<h2>Assumption register</h2>")
    parts.append("<table><tr><th>Key</th><th>Value</th><th>Source</th><th>Note</th></tr>")
    for assumption in assumptions:
        note = assumption.get("note") or ""
        parts.append(
            f"<tr><td>{_esc(assumption['key'])}</td><td>{_esc(assumption['value'])}</td>"
            f"<td>{_esc(assumption['source'])}</td><td>{_esc(note)}</td></tr>"
        )
    parts.append("</table>")
    parts.append("</section>")

    parts.append(_lineage_html(lineage))
    parts.append("</body></html>")
    return "".join(parts)
