"""Simple health-check router (ping)."""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/ping")
async def ping():
    """Return a simple health status."""
    return {"status": "ok", "message": "Server is running"}
