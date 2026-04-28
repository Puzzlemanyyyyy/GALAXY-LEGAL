"""Google Drive integration (Picker callback + fetch). Implemented by Emergent."""
from fastapi import APIRouter, Depends
from services.auth import get_current_user

router = APIRouter()


@router.get("/picker-config")
async def picker_config(user: dict = Depends(get_current_user)):
    """Return frontend config needed to initialize Google Picker."""
    from config import settings
    return {
        "apiKey": settings.GOOGLE_PICKER_API_KEY,
        "clientId": settings.GOOGLE_CLIENT_ID,
        "scope": "https://www.googleapis.com/auth/drive.file",
    }


# TODO (Emergent): POST /import (drive_file_ids[], case_id) → download, hash, store, extract, chunk, embed
