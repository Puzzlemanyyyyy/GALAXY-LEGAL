"""Auth-related backend endpoints. Login itself runs in the frontend with Supabase JS."""
from fastapi import APIRouter, Depends
from services.auth import get_current_user

router = APIRouter()


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """Return current authenticated user."""
    return {"id": user["id"], "email": user["email"]}
