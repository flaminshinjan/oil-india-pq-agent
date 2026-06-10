"""/api/voice/* — WebSocket route that hands the socket to Pipecat.

Single endpoint:
  ws://<backend>/api/voice/ws    real-time voice session

Each connection gets its own pipeline + LLM context (no cross-talk between
concurrent users). Keys read from env (DEEPGRAM_API_KEY, CARTESIA_API_KEY,
ANTHROPIC_API_KEY).
"""
from __future__ import annotations

import os

from fastapi import APIRouter, WebSocket

from ..voice.pipeline import run_voice_session


router = APIRouter(prefix="/api/voice")


@router.get("/status")
async def voice_status():
    """Health check the frontend uses to decide whether to show the mic
    button at all. We expose only whether keys are present — never the
    keys themselves."""
    return {
        "available": bool(os.getenv("DEEPGRAM_API_KEY") and os.getenv("CARTESIA_API_KEY")),
        "stt": "deepgram" if os.getenv("DEEPGRAM_API_KEY") else None,
        "tts": "cartesia" if os.getenv("CARTESIA_API_KEY") else None,
        "voice_id": os.getenv("CARTESIA_VOICE_ID"),
    }


@router.websocket("/ws")
async def voice_ws(websocket: WebSocket):
    """Browser opens this WebSocket and streams audio frames. Pipecat owns
    the protocol from here on. Optional `?domain=<key>` query string
    tells the LLM which dashboard the user is currently looking at."""
    domain = websocket.query_params.get("domain")
    await websocket.accept()
    try:
        await run_voice_session(websocket, domain=domain)
    except Exception as e:
        print(f"[voice] session ended with error: {e}")
        try:
            await websocket.close()
        except Exception:
            pass
