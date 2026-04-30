"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
async def health() -> dict[str, str]:
    """Liveness probe used by Docker / load balancers."""
    return {"status": "ok"}
