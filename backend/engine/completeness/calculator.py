from dataclasses import dataclass

from engine.completeness.catalog import FIELD_CATALOG, SECTIONS, Section

# How much a field's weight counts toward completeness, by source badge.
# registry/filing/user are full credit — Provision or the user directly
# confirmed the value. default/estimate are half credit — plausible but
# not confirmed. unknown is zero and is what "propagates to confidence":
# CONVENTIONS.md doesn't cover this directly, but the product spec is
# explicit that unknown must never block progress, only lower confidence.
SOURCE_CONFIDENCE: dict[str, float] = {
    "registry": 1.0,
    "filing": 1.0,
    "user": 1.0,
    "default": 0.5,
    "estimate": 0.5,
    "unknown": 0.0,
}


@dataclass(frozen=True)
class FieldState:
    key: str
    source: str


@dataclass(frozen=True)
class SectionCompleteness:
    section: Section
    confirmed_weight: float
    total_weight: float
    unknown_field_labels: tuple[str, ...]

    @property
    def score(self) -> float:
        if self.total_weight == 0:
            return 1.0
        return round(self.confirmed_weight / self.total_weight, 4)


@dataclass(frozen=True)
class CompletenessResult:
    overall_score: float
    sections: tuple[SectionCompleteness, ...]
    unknown_field_labels: tuple[str, ...]


def compute_completeness(field_states: dict[str, FieldState]) -> CompletenessResult:
    """Pure: same field_states in, same CompletenessResult out, every time.

    Fields present in FIELD_CATALOG but absent from field_states are
    treated as unknown (source="unknown") — a field nobody has touched
    yet counts against completeness exactly like an explicit "unknown"
    answer, so the meter reflects the profile's actual state.
    """
    by_section: dict[Section, list[tuple[float, float, str | None]]] = {
        section: [] for section in SECTIONS
    }

    for field in FIELD_CATALOG:
        state = field_states.get(field.key)
        source = state.source if state is not None else "unknown"
        confidence = SOURCE_CONFIDENCE.get(source, 0.0)
        confirmed = field.weight * confidence
        unknown_label = field.label if source == "unknown" else None
        by_section[field.section].append((confirmed, field.weight, unknown_label))

    sections = []
    all_unknown: list[str] = []
    total_confirmed = 0.0
    total_weight = 0.0
    for section in SECTIONS:
        entries = by_section[section]
        confirmed = sum(e[0] for e in entries)
        weight = sum(e[1] for e in entries)
        unknowns = tuple(e[2] for e in entries if e[2] is not None)
        sections.append(
            SectionCompleteness(
                section=section,
                confirmed_weight=confirmed,
                total_weight=weight,
                unknown_field_labels=unknowns,
            )
        )
        all_unknown.extend(unknowns)
        total_confirmed += confirmed
        total_weight += weight

    overall = round(total_confirmed / total_weight, 4) if total_weight else 1.0
    return CompletenessResult(
        overall_score=overall,
        sections=tuple(sections),
        unknown_field_labels=tuple(all_unknown),
    )
