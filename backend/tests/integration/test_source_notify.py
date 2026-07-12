import uuid

from db.session import set_rls_context
from services.notifications.email import StubEmailProvider
from services.sources.notify import notify_affected_memos
from services.sources.sweep import FlaggedMemo, SweepChange


def _create_tenant_and_workspace(client, codename="project-falcon"):
    slug = f"fund-{uuid.uuid4().hex[:8]}"
    tenant = client.post("/tenants", json={"name": "Fund A", "slug": slug})
    assert tenant.status_code == 201, tenant.text
    workspace = client.post(
        f"/tenants/{tenant.json()['id']}/workspaces", json={"codename": codename}
    )
    assert workspace.status_code == 201, workspace.text
    return workspace.json()


def test_notify_affected_memos_emails_workspace_owner(client_as, make_user, db_session):
    owner = make_user()
    client = client_as(owner)
    workspace = _create_tenant_and_workspace(client)
    tenant_id = uuid.UUID(workspace["tenant_id"])
    workspace_id = uuid.UUID(workspace["id"])

    changes = [
        SweepChange(
            curated_source_key="test-source",
            instrument_title="Test Act",
            instrument_id=uuid.uuid4(),
            old_instrument_version_id=uuid.uuid4(),
            new_instrument_version_id=uuid.uuid4(),
            flagged_memos=[
                FlaggedMemo(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    memo_id=uuid.uuid4(),
                    memo_title="Project Falcon — Impact Memo",
                    memo_version_id=uuid.uuid4(),
                )
            ],
        )
    ]

    provider = StubEmailProvider()
    set_rls_context(db_session, tenant_id, workspace_id)
    messages = notify_affected_memos(db_session, provider, changes)

    assert len(messages) == 1
    assert messages[0].to == owner.email
    assert "Project Falcon — Impact Memo" in messages[0].body
    assert provider.sent == messages


def test_notify_affected_memos_is_a_noop_with_no_changes(client_as, make_user, db_session):
    provider = StubEmailProvider()
    messages = notify_affected_memos(db_session, provider, [])
    assert messages == []
    assert provider.sent == []
