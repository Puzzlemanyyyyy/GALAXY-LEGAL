"""Concurrent draft insert race test.

Exercises the ``insert_draft_atomic`` RPC: spawns N concurrent calls for the
same (case_id, tipo_documento) and asserts they produce distinct, strictly
increasing version numbers.
"""
from __future__ import annotations

import asyncio
import pytest

from services.supabase_client import get_supabase_admin


def _rpc_available() -> bool:
    try:
        get_supabase_admin().rpc("insert_draft_atomic", {
            "p_case_id": "00000000-0000-0000-0000-000000000000",
            "p_run_id": None,
            "p_parent_id": None,
            "p_tipo": "initial_analysis",
            "p_content_md": "",
            "p_diff": None,
        }).execute()
    except Exception as e:
        msg = str(e)
        # The FK violation proves the RPC exists and was called.
        if "violates foreign key" in msg or "foreign key" in msg:
            return True
        # Any other error (not found, permission) → RPC is not callable yet.
        if "insert_draft_atomic" in msg or "PGRST202" in msg or "does not exist" in msg:
            return False
    return True


pytestmark = pytest.mark.skipif(
    not _rpc_available(),
    reason="insert_draft_atomic RPC not yet applied — apply /app/supabase/0002_phase2b.sql",
)


def _pick_case():
    admin = get_supabase_admin()
    rows = admin.table("cases").select("id").limit(1).execute().data or []
    if not rows:
        pytest.skip("No cases in DB")
    return rows[0]["id"]


@pytest.mark.asyncio
async def test_concurrent_atomic_inserts_are_unique():
    admin = get_supabase_admin()
    case_id = _pick_case()
    tipo = "jurisprudence_analysis"

    # Baseline max version before the race.
    before = (
        admin.table("drafts")
        .select("version")
        .eq("case_id", case_id)
        .eq("tipo_documento", tipo)
        .order("version", desc=True)
        .limit(1)
        .execute()
        .data or []
    )
    base = (before[0]["version"] if before else 0)

    def _call(i: int):
        return admin.rpc("insert_draft_atomic", {
            "p_case_id": case_id,
            "p_run_id": None,
            "p_parent_id": None,
            "p_tipo": tipo,
            "p_content_md": f"# Concurrent race {i}\n\nOne paragraph.",
            "p_diff": None,
        }).execute()

    results = await asyncio.gather(
        *[asyncio.to_thread(_call, i) for i in range(5)],
        return_exceptions=True,
    )
    versions = []
    inserted_ids = []
    for r in results:
        if isinstance(r, Exception):
            raise r
        data = r.data
        row = data if isinstance(data, dict) else (data[0] if data else None)
        assert row is not None
        versions.append(row["version"])
        inserted_ids.append(row["id"])

    try:
        assert len(set(versions)) == len(versions), f"collisions: {versions}"
        assert min(versions) == base + 1
        assert max(versions) == base + len(versions)
    finally:
        # Clean up inserted rows so re-runs stay green.
        for iid in inserted_ids:
            admin.table("drafts").delete().eq("id", iid).execute()
