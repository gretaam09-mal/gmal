import uuid

from sqlalchemy import select

from db.models import MetricsEvent
from db.session import raw_session
from services.metrics import EXPOSURE_LIST_GENERATED_EVENT


def _create_tenant_and_workspace(client, codename="project-falcon"):
    slug = f"fund-{uuid.uuid4().hex[:8]}"
    tenant = client.post("/tenants", json={"name": "Fund A", "slug": slug})
    assert tenant.status_code == 201, tenant.text
    workspace = client.post(
        f"/tenants/{tenant.json()['id']}/workspaces", json={"codename": codename}
    )
    assert workspace.status_code == 201, workspace.text
    return workspace.json()


def _set_profile_field(client, workspace_id, key, value, source="user"):
    resp = client.put(
        f"/workspaces/{workspace_id}/profile",
        json={"fields": [{"key": key, "value": value, "source": source}]},
    )
    assert resp.status_code == 200, resp.text


def test_first_analysis_records_time_to_exposure_list_metric(client_as, make_user, db_session):
    owner = make_user()
    client = client_as(owner)
    workspace = _create_tenant_and_workspace(client, codename="project-falcon")
    _set_profile_field(client, workspace["id"], "footprint.processes_personal_data", True)

    resp = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert resp.status_code == 201, resp.text

    with raw_session() as raw:
        events = raw.execute(
            select(MetricsEvent).where(MetricsEvent.event_name == EXPOSURE_LIST_GENERATED_EVENT)
        ).scalars().all()
    matching = [e for e in events if e.workspace_id == uuid.UUID(workspace["id"])]
    assert len(matching) == 1
    assert matching[0].properties["time_to_exposure_list_minutes"] >= 0


def test_second_analysis_does_not_duplicate_the_metric(client_as, make_user, db_session):
    owner = make_user()
    client = client_as(owner)
    workspace = _create_tenant_and_workspace(client, codename="project-condor")
    _set_profile_field(client, workspace["id"], "footprint.processes_personal_data", True)

    first = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert first.status_code == 201, first.text
    second = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert second.status_code == 201, second.text

    with raw_session() as raw:
        events = raw.execute(
            select(MetricsEvent).where(MetricsEvent.event_name == EXPOSURE_LIST_GENERATED_EVENT)
        ).scalars().all()
    matching = [e for e in events if e.workspace_id == uuid.UUID(workspace["id"])]
    assert len(matching) == 1
