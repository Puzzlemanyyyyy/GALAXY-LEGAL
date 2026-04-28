"""Document ingestion and management. Full implementation expanded by Emergent."""
from fastapi import APIRouter, Depends
from services.auth import get_current_user
from services.supabase_client import get_user_client

router = APIRouter()


@router.get("")
async def list_documents(case_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    res = (
        sb.table("case_documents")
        .select("*")
        .eq("case_id", case_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data


# TODO (Emergent): /upload, /process, /reindex, /chunks
