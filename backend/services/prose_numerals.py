"""Numeral extraction shared by every prompt whose output must trace back
to engine-produced figures (P-COMPOSE, P-DIFF-NOTE) — CONVENTIONS.md
rule 1.

Deliberately narrow: only tokens with a currency symbol, a decimal
point, a thousands-separator comma, or a trailing '%' are treated as
"numerals" here — bare small integers (clause numbers like "3(2)", years
like "2027") are left alone, since those are citations/dates, not
computed figures, and flagging them would make every legitimate clause
reference a false positive.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_NUMERAL_RE = re.compile(
    r"[£$€]\s?-?\d[\d,]*(?:\.\d+)?%?"  # currency-prefixed, e.g. £25,000.00
    r"|-?\d[\d,]*\.\d+%?"  # has a decimal point, e.g. 25000.00 or 12.5%
    r"|-?\d{1,3}(?:,\d{3})+%?"  # thousands-grouped with no currency symbol
    r"|-?\d+%"  # a bare percentage, e.g. 60%
)


def extract_numerals(text: str) -> list[str]:
    return _NUMERAL_RE.findall(text)


def normalise_numeral(token: str) -> Decimal | None:
    cleaned = token.strip().rstrip("%").lstrip("£$€ ").replace(",", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None
