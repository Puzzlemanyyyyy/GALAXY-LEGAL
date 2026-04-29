"""Supabase client factories.

- ``get_supabase_anon`` : public anon key, no JWT bound — used for token verification.
- ``get_supabase_admin``: service-role key — bypasses RLS, used ONLY for cost/audit
  and storage uploads on behalf of users (paths still scoped by user_id).
- ``get_user_client``   : anon client + the requester's JWT — RLS applies.
"""
from __future__ import annotations

from supabase import create_client, Client

from config import settings


def get_supabase_anon() -> Client:
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_ANON_KEY not configured")
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


def get_supabase_admin() -> Client:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY is not configured. "
            "Get it from Supabase dashboard → Settings → API and put it in backend/.env."
        )
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def get_user_client(access_token: str) -> Client:
    """Anon client scoped to the user's JWT — every query goes through RLS."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_ANON_KEY not configured")
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.postgrest.auth(access_token)
    return client
