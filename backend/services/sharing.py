"""Shareable read-only draft links.

Backed by the ``public.shared_drafts`` table (see
``/app/supabase/0002_phase2b.sql``). The public endpoint resolves a token
to a read-only payload (draft + evidences + minimal case context) and
never exposes owner/run ids or backend URLs.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from supabase import Client

from services.mappers import draft_to_api, evidence_to_api
from services.supabase_client import get_supabase_admin


EXPIRATION_OPTIONS = {
    "24h": timedelta(hours=24),
    "7d":  timedelta(days=7),
    "30d": timedelta(days=30),
    "never": None,
}


def create_share_token(
    *,
    draft_id: str,
    created_by: str,
    expires_in: str = "7d",
    watermark: Optional[str] = None,
) -> dict:
    if expires_in not in EXPIRATION_OPTIONS:
        raise ValueError(f"Invalid expires_in: {expires_in}. Options: {list(EXPIRATION_OPTIONS)}")
    delta = EXPIRATION_OPTIONS[expires_in]
    expires_at = (datetime.now(timezone.utc) + delta).isoformat() if delta else None

    admin = get_supabase_admin()
    row = (
        admin.table("shared_drafts")
        .insert({
            "draft_id": draft_id,
            "created_by": created_by,
            "expires_at": expires_at,
            "watermark": watermark,
        })
        .execute()
        .data[0]
    )
    return row


def list_share_tokens(*, draft_id: str, user_sb: Client) -> list[dict]:
    res = (
        user_sb.table("shared_drafts")
        .select("*")
        .eq("draft_id", draft_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


def revoke_share_token(*, token: str, user_sb: Client) -> bool:
    res = user_sb.table("shared_drafts").delete().eq("token", token).execute()
    return bool(res.data)


def resolve_public_draft(token: str) -> Optional[dict]:
    """Return the public payload for a token, or ``None`` if missing/expired."""
    admin = get_supabase_admin()
    try:
        share_q = admin.table("shared_drafts").select("*").eq("token", token).limit(1).execute()
    except Exception as exc:
        # Table missing (migration not applied) or any storage-layer failure:
        # surface as "not found" rather than 500.
        print(f"[sharing] resolve failed for token={token}: {exc}")
        return None
    if not share_q.data:
        return None
    share = share_q.data[0]
    expires_at = share.get("expires_at")
    if expires_at:
        exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if exp <= datetime.now(timezone.utc):
            return {"_expired": True, "token": token, "expires_at": expires_at}

    draft_q = admin.table("drafts").select("*").eq("id", share["draft_id"]).single().execute()
    if not draft_q.data:
        return None
    draft = draft_to_api(draft_q.data)

    evs: list[dict] = []
    run_id = draft_q.data.get("run_id")
    if run_id:
        ev_q = admin.table("evidences").select("*").eq("run_id", run_id).order("created_at").execute()
        evs = [evidence_to_api(r) for r in (ev_q.data or [])]

    # Fetch minimal case info (title, jurisdiccion, materia) — no owner details.
    case_q = admin.table("cases").select("id, title, jurisdiccion, materia").eq("id", draft_q.data["case_id"]).single().execute()
    case = case_q.data or {}

    # Best-effort view counter increment.
    try:
        admin.rpc("increment_share_view", {"p_token": token}).execute()
    except Exception:
        pass

    return {
        "token": token,
        "expires_at": expires_at,
        "watermark": share.get("watermark"),
        "view_count": share.get("view_count", 0),
        "case": {
            "title": case.get("title"),
            "jurisdiccion": case.get("jurisdiccion"),
            "materia": case.get("materia"),
        },
        "draft": {
            "title": draft.get("title"),
            "tipo_documento": draft.get("tipo_documento"),
            "version": draft.get("version"),
            "status": draft.get("status"),
            "content_md": draft.get("content_md"),
            "approved_at": draft.get("approved_at"),
        },
        "evidences": [
            {
                "external_id": e.get("external_id"),
                "page": e.get("page"),
                "paragraph": e.get("paragraph"),
                "quote_excerpt": e.get("quote_excerpt"),
                "verified": e.get("verified"),
            }
            for e in evs
        ],
    }
