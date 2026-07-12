"""Structural guardrail for F1: "tenancy middleware on EVERY backend route".

Walks every FastAPI route's dependency graph and asserts it depends on
get_workspace_membership (directly, or via require_role which itself
depends on it) — except a documented, narrow allowlist of routes that
are genuinely not about one workspace's data.
"""

from api.deps import get_workspace_membership
from api.main import app

# Routes that legitimately don't take a workspace_id at all:
#  - /health: no data, no auth.
#  - /roles: static role descriptions, no tenant data.
#  - /profile-field-catalog: static field catalog, no tenant data.
#  - POST /tenants, GET /tenants/{id}: tenant identity itself, not a
#    workspace's content (tenants aren't RLS-protected — see the RLS
#    migration's comment on why).
#  - /tenants/{id}/workspaces (GET+POST): listing/creating workspaces
#    *within* a tenant — scoped by tenant_id from the path, checked
#    against membership explicitly in the handler (see
#    api/routes/tenants.py::_can_create_workspace and
#    list_my_workspaces_in_tenant), rather than via the
#    get_workspace_membership dependency (there's no single workspace_id
#    yet — that's the point of these two endpoints).
#  - /invites/accept: the whole point is a user who isn't a member yet;
#    it derives tenant/workspace from a signed token instead (see
#    services/invites.py) and applies workspace_session itself.
#  - /me: the caller's own identity, not any workspace's data.
#  - /admin/*: F3's instrument-onboarding workbench. instruments/clauses/
#    obligations/predicates/cost_templates are shared reference data, not
#    tenant data (see db/models/regulatory.py's module docstring) — gated
#    by require_staff instead, which test_route_admin_gating.py checks.
_EXEMPT = {
    ("GET", "/health"),
    ("GET", "/me"),
    ("GET", "/roles"),
    ("GET", "/profile-field-catalog"),
    ("POST", "/tenants"),
    ("GET", "/tenants/{tenant_id}"),
    ("POST", "/tenants/{tenant_id}/workspaces"),
    ("GET", "/tenants/{tenant_id}/workspaces"),
    ("POST", "/invites/accept"),
    ("POST", "/admin/instruments"),
    ("GET", "/admin/instruments"),
    ("GET", "/admin/instruments/{instrument_id}"),
    ("GET", "/admin/instruments/{instrument_id}/obligations"),
    ("POST", "/admin/clauses/{clause_id}/obligations/extract"),
    ("PATCH", "/admin/obligations/{obligation_id}"),
    ("POST", "/admin/obligations/{obligation_id}/approve"),
    ("POST", "/admin/obligations/{obligation_id}/correct"),
    ("POST", "/admin/obligations/{obligation_id}/predicates/draft"),
    ("POST", "/admin/obligations/{obligation_id}/predicates"),
    ("GET", "/admin/obligations/{obligation_id}/predicates"),
    ("PATCH", "/admin/predicates/{predicate_id}"),
    ("POST", "/admin/predicates/{predicate_id}/test"),
    ("POST", "/admin/predicates/{predicate_id}/approve"),
    ("POST", "/admin/obligations/{obligation_id}/cost-template"),
    ("GET", "/admin/obligations/{obligation_id}/cost-template"),
    ("GET", "/admin/metrics/onboarding"),
}


def _dependency_closure(dependant) -> set:
    seen = set()
    stack = [dependant]
    while stack:
        current = stack.pop()
        for sub in current.dependencies:
            if sub.call not in seen:
                seen.add(sub.call)
                stack.append(sub)
    return seen


def test_every_non_exempt_route_depends_on_workspace_membership():
    checked = []
    for route in app.routes:
        methods = getattr(route, "methods", None)
        dependant = getattr(route, "dependant", None)
        if not methods or dependant is None:
            continue
        for method in methods:
            if method == "HEAD":
                continue
            key = (method, route.path)
            if key in _EXEMPT:
                continue
            checked.append(key)
            closure = _dependency_closure(dependant)
            assert get_workspace_membership in closure, (
                f"{method} {route.path} does not depend on get_workspace_membership "
                "(add it, or add the route to the documented _EXEMPT allowlist with a reason)"
            )

    # Sanity check: we actually verified a non-trivial number of routes,
    # so this test can't silently pass by finding nothing to check.
    assert len(checked) >= 10
