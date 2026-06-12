from fastapi import APIRouter
from app.core.database import get_db

router = APIRouter()


@router.get("")
async def health_check():
    try:
        db = get_db()
        await db.command("ping")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    return {"status": "ok", "db": db_status}
