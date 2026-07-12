"""Structural guardrail for F3: every /admin/* route must be staff-gated.

Mirrors test_route_tenancy_enforcement.py's approach — walks each route's
dependency graph rather than trusting a convention to hold by hand.
"""

from api.deps import require_staff
from api.main import app


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


def test_every_admin_route_depends_on_require_staff():
    checked = []
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None)
        dependant = getattr(route, "dependant", None)
        if not path.startswith("/admin") or not methods or dependant is None:
            continue
        for method in methods:
            if method == "HEAD":
                continue
            checked.append((method, path))
            closure = _dependency_closure(dependant)
            assert require_staff in closure, (
                f"{method} {path} does not depend on require_staff — every /admin "
                "route must be staff-gated (see CONVENTIONS.md and F3's spec: "
                "internal, staff-gated /admin only, never linked from the client UI)"
            )

    # Sanity check: this test can't silently pass by finding no admin routes.
    assert len(checked) >= 10


def test_no_non_admin_route_depends_on_require_staff():
    """The inverse check: require_staff is /admin's gate specifically, not
    a general-purpose dependency that might get attached somewhere odd
    and quietly change a tenant-facing route's access model."""
    for route in app.routes:
        path = getattr(route, "path", "")
        dependant = getattr(route, "dependant", None)
        if path.startswith("/admin") or dependant is None:
            continue
        closure = _dependency_closure(dependant)
        assert require_staff not in closure, f"{path} unexpectedly depends on require_staff"
