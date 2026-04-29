"""Audit log helper. Uses the admin (service-role) client so writes
succeed regardless of RLS — but never expose this client elsewhere.
"""
from __future__ import annotations

from typing import Any

from supabase import Client

from .supabase_client import get_supabase_admin


def log(
    *,
    actor_id: str | None,
    action: str,
    case_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    payload: dict[str, Any] | None = None,
    client: Client | None = None,
) -> None:
    sb = client or _safe_admin()
    if sb is None:
        return  # graceful no-op when service-role key missing
    try:
        sb.table("audit_log").insert({
            "actor_id": actor_id,
            "case_id": case_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "payload": payload or {},
        }).execute()
    except Exception as exc:  # never let audit break the main flow
        print(f"[audit] failed to write entry action={action}: {exc}")


def _safe_admin() -> Client | None:
    try:
        return get_supabase_admin()
    except Exception:
        return None
