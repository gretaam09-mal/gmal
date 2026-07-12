import uuid
from datetime import UTC, datetime

from db.models import Memo, MetricsEvent, Tenant, Workspace
from db.session import set_rls_context
from services.metrics import (
    ASSUMPTION_OVERRIDDEN_EVENT,
    EXPOSURE_LIST_GENERATED_EVENT,
    MEMO_APPROVED_EVENT,
    REVIEW_COMPLETED_EVENT,
)
from services.metrics_report import generate_monthly_metrics_report
from services.onboarding_metrics import ONBOARDING_COMPLETED_EVENT


def _create_tenant_and_workspace(client, codename="project-falcon"):
    slug = f"fund-{uuid.uuid4().hex[:8]}"
    tenant = client.post("/tenants", json={"name": "Fund A", "slug": slug})
    assert tenant.status_code == 201, tenant.text
    workspace = client.post(
        f"/tenants/{tenant.json()['id']}/workspaces", json={"codename": codename}
    )
    assert workspace.status_code == 201, workspace.text
    return workspace.json()


def _event(name, properties, created_at):
    return MetricsEvent(event_name=name, properties=properties, created_at=created_at)


def test_generate_monthly_metrics_report_aggregates_events_in_period(
    client_as, make_user, db_session
):
    owner = make_user()
    client = client_as(owner)
    _create_tenant_and_workspace(client, codename="project-falcon")

    in_period = datetime(2027, 3, 15, tzinfo=UTC)
    out_of_period = datetime(2027, 2, 15, tzinfo=UTC)

    db_session.add_all(
        [
            _event(
                EXPOSURE_LIST_GENERATED_EVENT,
                {"time_to_exposure_list_minutes": 100},
                in_period,
            ),
            _event(
                EXPOSURE_LIST_GENERATED_EVENT,
                {"time_to_exposure_list_minutes": 200},
                in_period,
            ),
            _event(
                EXPOSURE_LIST_GENERATED_EVENT,
                {"time_to_exposure_list_minutes": 9999},
                out_of_period,
            ),
            _event(MEMO_APPROVED_EVENT, {"time_to_approved_memo_minutes": 60}, in_period),
            _event(REVIEW_COMPLETED_EVENT, {"review_minutes": 30}, in_period),
            _event(
                ONBOARDING_COMPLETED_EVENT,
                {"instrument_id": "x", "onboarding_hours": 4},
                in_period,
            ),
            _event(ASSUMPTION_OVERRIDDEN_EVENT, {"assumption_key": "a"}, in_period),
            _event(ASSUMPTION_OVERRIDDEN_EVENT, {"assumption_key": "b"}, in_period),
        ]
    )
    db_session.commit()

    report = generate_monthly_metrics_report(db_session, year=2027, month=3)

    assert report.time_to_exposure_list_minutes_avg == 150.0
    assert report.time_to_approved_memo_minutes_avg == 60.0
    assert report.review_minutes_avg == 30.0
    assert report.onboarding_hours_avg == 4.0
    assert report.override_count == 2
    assert report.memos_approved_count == 1
    assert report.used_in_ic_count == 0


def test_generate_monthly_metrics_report_is_empty_when_nothing_happened(
    client_as, make_user, db_session
):
    report = generate_monthly_metrics_report(db_session, year=2099, month=1)

    assert report.time_to_exposure_list_minutes_avg is None
    assert report.time_to_approved_memo_minutes_avg is None
    assert report.review_minutes_avg is None
    assert report.onboarding_hours_avg is None
    assert report.override_count == 0
    assert report.memos_approved_count == 0
    assert report.used_in_ic_count == 0


def test_generate_monthly_metrics_report_counts_used_in_ic_memos_across_tenants(
    client_as, make_user, db_session
):
    owner = make_user()
    tenant = Tenant(name="Fund A", slug=f"fund-{uuid.uuid4().hex[:8]}", created_by_user_id=owner.id)
    db_session.add(tenant)
    db_session.flush()
    set_rls_context(db_session, tenant.id, None)
    workspace = Workspace(
        tenant_id=tenant.id, codename="project-falcon", created_by_user_id=owner.id
    )
    db_session.add(workspace)
    db_session.flush()
    set_rls_context(db_session, tenant.id, workspace.id)

    in_period = datetime(2027, 4, 10, tzinfo=UTC)
    db_session.add_all(
        [
            Memo(
                tenant_id=tenant.id,
                workspace_id=workspace.id,
                title="Used in IC",
                created_by_user_id=owner.id,
                used_in_ic=True,
                created_at=in_period,
            ),
            Memo(
                tenant_id=tenant.id,
                workspace_id=workspace.id,
                title="Not used",
                created_by_user_id=owner.id,
                used_in_ic=False,
                created_at=in_period,
            ),
        ]
    )
    db_session.commit()

    report = generate_monthly_metrics_report(db_session, year=2027, month=4)

    assert report.used_in_ic_count == 1
