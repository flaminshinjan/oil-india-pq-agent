"""FastAPI app: a single streaming chat endpoint plus a few read-only helpers.

The chat endpoint runs the LangGraph agent and forwards every event of
interest (assistant text, tool calls, tool results) as newline-delimited JSON
to the browser. The frontend renders each `type` as a distinct message block.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from .agent import get_graph, build_system_prompt
from .config import settings
from .schemas import (
    ChatRequest,
    WireDone,
    WireError,
    WireText,
    WireToolCall,
    WireToolResult,
)
from .vectorstore import get_store


app = FastAPI(title="Oil India PQ Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _warm_in_background() -> None:
    """Fire and forget a tiny embed call so the SentenceTransformer model
    and Chroma collections are loaded before the first user query — without
    blocking the /api/health probe.
    """

    async def _warm() -> None:
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: get_store().embed(["warmup"]))
            print("[warmup] embedder + chroma ready")
        except Exception as e:
            print(f"[warmup] failed (will retry on first request): {e}")

    asyncio.create_task(_warm())


@app.get("/api/health")
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


@app.get("/api/sources")
async def sources():
    from .tools import list_available_sources
    return list_available_sources.invoke({})


def _to_lc_messages(req: ChatRequest):
    msgs = [SystemMessage(content=build_system_prompt())]
    for m in req.messages:
        if m.role == "user":
            msgs.append(HumanMessage(content=m.content))
        else:
            msgs.append(AIMessage(content=m.content))
    return msgs


def _wire(obj) -> bytes:
    return (obj.model_dump_json() + "\n").encode("utf-8")


async def _run_chat(req: ChatRequest) -> AsyncIterator[bytes]:
    graph = get_graph()
    initial = {"messages": _to_lc_messages(req)}
    # Allow up to ~12 llm↔tools cycles before LangGraph terminates the run.
    run_config = {"recursion_limit": 40}

    citations: list[dict] = []
    seen_tool_calls: set[str] = set()
    seen_tool_results: set[str] = set()
    last_text = ""

    try:
        async for event in graph.astream_events(initial, version="v2", config=run_config):
            kind = event.get("event")

            # ---- token-level streaming for assistant text ----
            if kind == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk is None:
                    continue
                # AIMessageChunk.content can be str OR a list of blocks
                piece = _extract_text_from_chunk(chunk)
                if piece:
                    last_text += piece
                    yield _wire(WireText(delta=piece))

            # ---- tool call announced by the model ----
            elif kind == "on_tool_start":
                name = event.get("name", "")
                inp = event["data"].get("input") or {}
                run_id = str(event.get("run_id") or uuid.uuid4())
                if run_id in seen_tool_calls:
                    continue
                seen_tool_calls.add(run_id)
                yield _wire(WireToolCall(id=run_id, name=name, args=_safe(inp)))

            # ---- tool execution result ----
            elif kind == "on_tool_end":
                name = event.get("name", "")
                out = event["data"].get("output")
                run_id = str(event.get("run_id") or uuid.uuid4())
                if run_id in seen_tool_results:
                    continue
                seen_tool_results.add(run_id)
                result = _normalize_tool_output(out)
                # Pull citations out of search results
                for r in (result.get("results") or []) if isinstance(result, dict) else []:
                    if isinstance(r, dict) and r.get("filename"):
                        citations.append({
                            "filename": r.get("filename"),
                            "source": r.get("source"),
                            "section": r.get("section"),
                            "session": r.get("session"),
                            "tool": name,
                        })
                yield _wire(WireToolResult(id=run_id, name=name, result=result))

        # Dedupe citations by (filename, section)
        seen_keys = set()
        unique = []
        for c in citations:
            key = (c.get("filename"), c.get("section"))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            unique.append(c)
        yield _wire(WireDone(citations=unique))

    except Exception as e:
        yield _wire(WireError(message=f"{type(e).__name__}: {e}"))


def _extract_text_from_chunk(chunk) -> str:
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    # Anthropic returns lists of content blocks
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return ""


def _normalize_tool_output(out) -> dict:
    """ToolNode returns the tool's raw output; older paths wrap it in a
    ToolMessage. Coerce to a dict for the wire."""
    if isinstance(out, ToolMessage):
        try:
            return json.loads(out.content)
        except Exception:
            return {"text": str(out.content)}
    if isinstance(out, dict):
        return _safe(out)
    if isinstance(out, str):
        try:
            return json.loads(out)
        except Exception:
            return {"text": out}
    return {"text": str(out)}


def _safe(obj):
    """Best-effort JSON coercion for tool inputs (Pydantic models, etc.)."""
    try:
        json.dumps(obj)
        return obj
    except Exception:
        pass
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe(v) for v in obj]
    return str(obj)


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not req.messages:
        raise HTTPException(400, "messages must not be empty")
    if not settings.anthropic_api_key:
        raise HTTPException(
            500,
            "ANTHROPIC_API_KEY not configured on the server (see backend/.env)",
        )
    return StreamingResponse(
        _run_chat(req),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no"},
    )
