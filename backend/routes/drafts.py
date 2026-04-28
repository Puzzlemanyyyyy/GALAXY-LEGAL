"""Drafts management with versioning + diff. Full logic via Emergent."""
from fastapi import APIRouter, Depends
from services.auth import get_current_user
from services.supabase_client import get_user_client

router = APIRouter()


@router.get("")
async def list_drafts(case_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    res = (
        sb.table("drafts")
        .select("*")
        .eq("case_id", case_id)
        .order("version", desc=True)
        .execute()
    )
    return res.data


# TODO (Emergent): POST /drafts/{id}/revision (computes diff), /approve, /export-docx
