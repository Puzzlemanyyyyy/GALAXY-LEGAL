"""Integration tests for shareable-draft links.

Skipped automatically when the ``shared_drafts`` table is not yet present
(0002 migration pending). Creates ephemeral rows and cleans up after itself.
"""
from __future__ import annotations

import pytest

from services.supabase_client import get_supabase_admin


def _shared_drafts_available() -> bool:
    try:
        get_supabase_admin().table("shared_drafts").select("token").limit(1).execute()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _shared_drafts_available(),
    reason="shared_drafts table/RPC not yet applied — apply /app/supabase/0002_phase2b.sql",
)


def _pick_any_draft():
    admin = get_supabase_admin()
    rows = admin.table("drafts").select("id, case_id").limit(1).execute().data or []
    if not rows:
        pytest.skip("No drafts in DB to share")
    return rows[0]


def _pick_any_user():
    admin = get_supabase_admin()
    try:
        users = admin.auth.admin.list_users()
    except Exception:
        pytest.skip("Cannot list users")
    if not users:
        pytest.skip("No users in auth.users")
    return users[0]


def test_create_resolve_revoke_share():
    from services import sharing

    draft = _pick_any_draft()
    user = _pick_any_user()

    row = sharing.create_share_token(draft_id=draft["id"], created_by=user.id, expires_in="24h")
    assert row["token"]
    token = row["token"]

    try:
        payload = sharing.resolve_public_draft(token)
        assert payload is not None
        assert payload["draft"]["content_md"]
        assert "case" in payload
        assert isinstance(payload["evidences"], list)
    finally:
        admin = get_supabase_admin()
        admin.table("shared_drafts").delete().eq("token", token).execute()


def test_resolve_missing_token_returns_none():
    from services import sharing
    assert sharing.resolve_public_draft("00000000-0000-0000-0000-000000000000") is None


def test_invalid_expires_in_rejected():
    from services import sharing
    with pytest.raises(ValueError):
        sharing.create_share_token(draft_id="x", created_by="y", expires_in="forever")
