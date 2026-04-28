"""Cases (expedientes) CRUD."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services.auth import get_current_user
from services.supabase_client import get_user_client

router = APIRouter()


class CaseCreate(BaseModel):
    title: str
    reference: Optional[str] = None
    jurisdiccion: Optional[str] = None
    materia: Optional[str] = None
    description: Optional[str] = None


class CaseUpdate(BaseModel):
    title: Optional[str] = None
    reference: Optional[str] = None
    jurisdiccion: Optional[str] = None
    materia: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


@router.get("")
async def list_cases(user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    res = sb.table("cases").select("*").order("created_at", desc=True).execute()
    return res.data


@router.post("", status_code=201)
async def create_case(payload: CaseCreate, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    res = sb.table("cases").insert({
        **payload.model_dump(exclude_none=True),
        "owner_id": user["id"],
    }).execute()
    if not res.data:
        raise HTTPException(500, "Failed to create case")
    return res.data[0]


@router.get("/{case_id}")
async def get_case(case_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    res = sb.table("cases").select("*").eq("id", case_id).single().execute()
    if not res.data:
        raise HTTPException(404, "Case not found")
    return res.data


@router.patch("/{case_id}")
async def update_case(case_id: str, payload: CaseUpdate, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    res = sb.table("cases").update(
        payload.model_dump(exclude_none=True)
    ).eq("id", case_id).execute()
    if not res.data:
        raise HTTPException(404, "Case not found")
    return res.data[0]


@router.delete("/{case_id}", status_code=204)
async def delete_case(case_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    sb.table("cases").delete().eq("id", case_id).execute()
    return None
