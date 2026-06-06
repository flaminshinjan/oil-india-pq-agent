"""/api/health and /api/sources — operational read endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from ..agents.tools import list_available_sources
from ..config import settings
from ..retrieval.vectorstore import get_store


router = APIRouter()


@router.get("/api/health")
async def health():
    try:
        stats = get_store().stats()
    except Exception as e:
        stats = {"error": str(e)}
    key = settings.anthropic_api_key
    key_ok = bool(key) and not key.startswith("sk-ant-your-")
    return {
        "status": "ok",
        "model": settings.anthropic_model,
        "anthropic_key_set": key_ok,
        "vector_store": stats,
    }


@router.get("/api/sources")
async def sources():
    return list_available_sources.invoke({})
