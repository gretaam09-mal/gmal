from dataclasses import dataclass

Section = str  # "identity_scale" | "activity" | "footprint" | "cost_sketch" | "materiality"


@dataclass(frozen=True)
class FieldSpec:
    key: str
    section: Section
    label: str
    weight: float = 1.0
    used_for: str | None = None
    """Plain-language reason a footprint flag exists, shown next to it in
    the guided editor — e.g. "Determines whether UK GDPR applies."""


FIELD_CATALOG: tuple[FieldSpec, ...] = (
    # Identity & Scale — auto-filled from Companies House, confirmable.
    FieldSpec("identity.company_name", "identity_scale", "Company name"),
    FieldSpec("identity.company_number", "identity_scale", "Companies House number"),
    FieldSpec("identity.company_status", "identity_scale", "Registration status", weight=0.5),
    FieldSpec("identity.incorporated_on", "identity_scale", "Incorporated on", weight=0.5),
    FieldSpec("identity.officers", "identity_scale", "Officers", weight=0.5),
    FieldSpec("scale.band", "identity_scale", "Scale band (filing-derived)"),
    FieldSpec("scale.employee_count", "identity_scale", "Employee count"),
    FieldSpec("scale.annual_revenue_gbp", "identity_scale", "Annual revenue (GBP)"),
    # Activity — sector taxonomy.
    FieldSpec("activity.sector", "activity", "Primary sector"),
    FieldSpec("activity.sic_codes", "activity", "SIC codes", weight=0.5),
    FieldSpec("activity.description", "activity", "Activity description", weight=0.5),
    # Footprint — plain yes/no/unknown questions, each tied to why it matters.
    FieldSpec(
        "footprint.has_overseas_operations",
        "footprint",
        "Operates outside the UK?",
        used_for="Determines whether cross-border regulatory regimes apply.",
    ),
    FieldSpec(
        "footprint.processes_personal_data",
        "footprint",
        "Processes personal data at scale?",
        used_for="Triggers UK GDPR / data protection exposure.",
    ),
    FieldSpec(
        "footprint.holds_client_money",
        "footprint",
        "Holds client money or assets?",
        used_for="Triggers FCA client money rules.",
    ),
    FieldSpec(
        "footprint.employs_staff",
        "footprint",
        "Employs staff directly?",
        used_for="Triggers employment law obligations.",
    ),
    FieldSpec(
        "footprint.regulated_activity",
        "footprint",
        "Carries out an FCA/PRA-regulated activity?",
        used_for="Determines whether financial services regulation applies.",
    ),
    FieldSpec(
        "footprint.handles_hazardous_materials",
        "footprint",
        "Handles hazardous materials or waste?",
        used_for="Triggers environmental regulation exposure.",
    ),
    # Cost sketch — labelled defaults, editable.
    FieldSpec(
        "cost_sketch.compliance_headcount", "cost_sketch", "Compliance headcount", weight=0.5
    ),
    FieldSpec(
        "cost_sketch.annual_compliance_spend_gbp",
        "cost_sketch",
        "Annual compliance spend (GBP, estimate)",
        weight=0.5,
    ),
    # Materiality.
    FieldSpec("materiality.threshold_gbp", "materiality", "Materiality threshold (GBP)"),
)

FIELD_BY_KEY: dict[str, FieldSpec] = {field.key: field for field in FIELD_CATALOG}

SECTIONS: tuple[Section, ...] = (
    "identity_scale",
    "activity",
    "footprint",
    "cost_sketch",
    "materiality",
)
