"""FastAPI entry point for Atlas — OIL Intelligence OS.

This module is intentionally thin:
  - Build the FastAPI app + CORS.
  - Register the three routers (chat, os, health).
  - Wire startup hooks: init the signals store, warm the embedder, run
    an initial agent scan so the first morning-brief request is instant.

All domain logic lives in `api/`, `agents/`, `orchestrator/`, `core/`,
`retrieval/`. This file should never need to grow.
"""
from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import chat as chat_router
from .api import health as health_router
from .api import os as os_router
from .config import settings
from .core import signals as signals_store
from .orchestrator import brief as brief_module
from .retrieval.vectorstore import get_store


app = FastAPI(title="Atlas — OIL Intelligence OS", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router.router)
app.include_router(chat_router.router)
app.include_router(os_router.router)


# ------------------------------------------------------------------
# Startup hooks
# ------------------------------------------------------------------

@app.on_event("startup")
async def _init_signals_store() -> None:
    """Create the signals SQLite table on first boot."""
    signals_store.init()


@app.on_event("startup")
async def _initial_scan() -> None:
    """Populate the signals table once at boot so the very first request
    to /api/os/brief returns instantly without waiting for agent scans."""

    async def _go() -> None:
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, brief_module.refresh_signals)
            print("[orchestrator] initial scan complete")
        except Exception as e:
            print(f"[orchestrator] initial scan failed: {e}")

    asyncio.create_task(_go())


@app.on_event("startup")
async def _warm_in_background() -> None:
    """Pre-load the SentenceTransformer model + Chroma collections before
    the first user query — without blocking /api/health."""

    async def _warm() -> None:
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: get_store().embed(["warmup"]))
            print("[warmup] embedder + chroma ready")
        except Exception as e:
            print(f"[warmup] failed (will retry on first request): {e}")

    asyncio.create_task(_warm())
