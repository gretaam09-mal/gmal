import uuid

from services.error_register import (
    add_affected_workspace,
    create_error_entry,
    list_error_entries,
    resolve_error_entry,
    send_disclosure,
    set_root_cause,
)
from services.notifications.email import StubEmailProvider


def test_create_and_list_error_entries(db_session):
    entry = create_error_entry(
        db_session,
        source="memo_composition",
        message="A cost figure did not trace to an engine value.",
        context={"memo_version_id": str(uuid.uuid4())},
    )
    db_session.commit()

    assert entry.resolved_at is None
    assert entry.root_cause is None
    assert entry.affected_workspace_ids == []

    unresolved = list_error_entries(db_session, resolved=False)
    assert entry.id in {e.id for e in unresolved}
    resolved = list_error_entries(db_session, resolved=True)
    assert entry.id not in {e.id for e in resolved}


def test_root_cause_and_resolve_lifecycle(db_session):
    entry = create_error_entry(db_session, source="sweep", message="Duplicate obligation.")
    db_session.commit()

    set_root_cause(db_session, entry=entry, root_cause="A race in the sweep's dedup check.")
    db_session.commit()
    assert entry.root_cause == "A race in the sweep's dedup check."

    resolve_error_entry(db_session, entry=entry)
    db_session.commit()
    assert entry.resolved_at is not None

    resolved = list_error_entries(db_session, resolved=True)
    assert entry.id in {e.id for e in resolved}


def test_add_affected_workspace_is_idempotent(db_session):
    entry = create_error_entry(db_session, source="memo_composition", message="Bad figure.")
    workspace_id = uuid.uuid4()

    add_affected_workspace(db_session, entry=entry, workspace_id=workspace_id)
    add_affected_workspace(db_session, entry=entry, workspace_id=workspace_id)
    db_session.commit()

    assert entry.affected_workspace_ids == [str(workspace_id)]


def test_send_disclosure_emails_every_affected_workspaces_owners(client_as, make_user, db_session):
    owner = make_user()
    client = client_as(owner)
    slug = f"fund-{uuid.uuid4().hex[:8]}"
    tenant_resp = client.post("/tenants", json={"name": "Fund A", "slug": slug})
    assert tenant_resp.status_code == 201, tenant_resp.text
    workspace_resp = client.post(
        f"/tenants/{tenant_resp.json()['id']}/workspaces", json={"codename": "project-falcon"}
    )
    assert workspace_resp.status_code == 201, workspace_resp.text
    workspace = workspace_resp.json()
    tenant_id = uuid.UUID(workspace["tenant_id"])
    workspace_id = uuid.UUID(workspace["id"])

    entry = create_error_entry(db_session, source="memo_composition", message="Bad figure.")
    add_affected_workspace(db_session, entry=entry, workspace_id=workspace_id)
    db_session.commit()

    provider = StubEmailProvider()
    entry, messages = send_disclosure(
        db_session,
        entry=entry,
        disclosure_note="A memo you received understated exposure by 12%; corrected version "
        "attached.",
        email_provider=provider,
        affected_tenant_ids_by_workspace={str(workspace_id): tenant_id},
    )
    db_session.commit()

    assert entry.disclosure_sent_at is not None
    assert entry.disclosure_note.startswith("A memo you received")
    assert len(messages) == 1
    assert messages[0].to == owner.email
    assert provider.sent == messages


def test_send_disclosure_skips_workspaces_without_a_known_tenant(db_session):
    entry = create_error_entry(db_session, source="sweep", message="Bad figure.")
    workspace_id = uuid.uuid4()
    add_affected_workspace(db_session, entry=entry, workspace_id=workspace_id)
    db_session.commit()

    provider = StubEmailProvider()
    entry, messages = send_disclosure(
        db_session,
        entry=entry,
        disclosure_note="note",
        email_provider=provider,
        affected_tenant_ids_by_workspace={},
    )

    assert messages == []
    assert entry.disclosure_sent_at is not None
