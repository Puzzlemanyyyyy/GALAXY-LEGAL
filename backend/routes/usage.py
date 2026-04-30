"""Monthly OpenAI usage summary for the current user."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from services.auth import get_current_user
from services.budget import get_current_usage


router = APIRouter()


@router.get("/current")
async def current_usage(user: dict = Depends(get_current_user)):
    return get_current_usage(owner_id=user["id"]).as_dict()
