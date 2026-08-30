"""AI_ROUTING: which provider serves which task, and how sensitive that
task's data is — see docs/Provision_Kimi_Integration_Spec.md section 3.
validate_routing is the load-time half of the confidentiality gate: it
refuses to let this table itself claim a confidential task can be served
by a provider that isn't confidential_ok, so a bad edit here fails at
process start (or first router use), not the first time a real call
happens to hit that task. The runtime half — checked against the
data_class the *caller* declares on each individual call, independent of
what this table says — is services.ai.providers.ensure_data_class_allowed,
applied in services/ai/router.py.
"""
from __future__ import annotations

from dataclasses import dataclass

from services.ai.errors import AIRoutingConfigError
from services.ai.providers import AIProvider, DataClass


@dataclass(frozen=True)
class TaskRoute:
    primary: str
    fallback: str
    data_class: DataClass


# Spec section 3's example table names a "claude_fallback" provider for
# confidential tasks — a second, independently-configured confidential_ok
# provider for redundancy. This PR registers exactly the two providers the
# implementation was scoped to (claude, kimi — see services/ai/router.py's
# default registry), so every confidential task's fallback is "claude"
# itself here: with only one confidential_ok provider registered, a
# confidential task genuinely has nowhere else it's allowed to fall back
# to. AIRouter dedupes an identical primary/fallback into a single
# attempt (see router.py) rather than retrying the same provider twice.
# Add a real second confidential_ok provider (a second Claude profile, or
# kimi_selfhosted per spec section 2) before giving a confidential task an
# actual fallback.
#
# diff_note isn't in the spec's example table, but P-DIFF-NOTE summarises
# a diff between two versions of one client's memo — clearly confidential
# by the same rule as memo_composition/cost_estimation — so it's added
# here on the same principle the spec states in section 0/1.
#
# horizon_summary and trajectory_hypo have no caller yet (see
# docs/Provision_Kimi_Integration_Spec.md section 1) — they're config-only
# until those features exist, validated the same as every other entry.
AI_ROUTING: dict[str, TaskRoute] = {
    "extraction": TaskRoute(primary="kimi", fallback="claude", data_class="public"),
    "rule_drafting": TaskRoute(primary="kimi", fallback="claude", data_class="public"),
    "horizon_summary": TaskRoute(primary="kimi", fallback="claude", data_class="public"),
    "memo_composition": TaskRoute(primary="claude", fallback="claude", data_class="confidential"),
    "cost_estimation": TaskRoute(primary="claude", fallback="claude", data_class="confidential"),
    "trajectory_hypo": TaskRoute(primary="claude", fallback="claude", data_class="confidential"),
    "diff_note": TaskRoute(primary="claude", fallback="claude", data_class="confidential"),
}


def validate_routing(providers: dict[str, AIProvider], routing: dict[str, TaskRoute]) -> None:
    """Fails fast on two ways this config can be wrong: a task naming a
    provider that was never registered, and a confidential task naming a
    primary or fallback that isn't confidential_ok. Called once, by
    AIRouter.__init__ — see services/ai/router.py."""
    for task, route in routing.items():
        for role, provider_name in (("primary", route.primary), ("fallback", route.fallback)):
            provider = providers.get(provider_name)
            if provider is None:
                raise AIRoutingConfigError(
                    f"AI_ROUTING[{task!r}].{role} names unregistered provider "
                    f"{provider_name!r} — registered providers: {sorted(providers)}"
                )
            if route.data_class == "confidential" and not provider.confidential_ok:
                raise AIRoutingConfigError(
                    f"AI_ROUTING[{task!r}] is data_class='confidential' but its "
                    f"{role} provider {provider_name!r} has confidential_ok=False — "
                    f"a confidential task may never name a provider that isn't "
                    f"confidential_ok, even as a fallback."
                )
