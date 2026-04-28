"""FastAPI dependency to authenticate requests via Supabase JWT."""
from fastapi import Header, HTTPException, status
from services.supabase_client import get_supabase_anon


async def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
        )
    token = authorization.split(" ", 1)[1]
    try:
        client = get_supabase_anon()
        user_resp = client.auth.get_user(token)
        if not user_resp or not user_resp.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )
        return {
            "id": user_resp.user.id,
            "email": user_resp.user.email,
            "token": token,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Auth failed: {e}",
        )
