"""/api/chat — streaming NDJSON chat for the PQ Drafting agent.

Streams four event types over the wire (text, tool_call, tool_result, done)
plus error. The frontend renders each one as a distinct UI block.
"""
from __future__ import annotations

import json
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from ..agents.pq import get_fast_graph, get_graph, is_report_request, system_prompt
from ..config import settings
from ..schemas.wire import (
    ChatRequest,
    WireDone,
    WireError,
    WireText,
    WireToolCall,
    WireToolResult,
)


router = APIRouter()


def _to_lc_messages(req: ChatRequest):
    msgs = [SystemMessage(content=system_prompt())]
    for m in req.messages:
        if m.role == "user":
            msgs.append(HumanMessage(content=m.content))
        else:
            msgs.append(AIMessage(content=m.content))
    return msgs


def _wire(obj) -> bytes:
    return (obj.model_dump_json() + "\n").encode("utf-8")


async def _run_chat(req: ChatRequest) -> AsyncIterator[bytes]:
    # A PDF/report request is dominated by streaming a large generate_report
    # payload, so run it on the faster model; everything else stays on the
    # guardrail-strong main model.
    last_user = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
    graph = get_fast_graph() if is_report_request(last_user) else get_graph()
    initial = {"messages": _to_lc_messages(req)}
    run_config = {"recursion_limit": 40}

    citations: list[dict] = []
    seen_tool_calls: set[str] = set()
    seen_tool_results: set[str] = set()

    try:
        async for event in graph.astream_events(initial, version="v2", config=run_config):
            kind = event.get("event")

            if kind == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk is None:
                    continue
                piece = _extract_text_from_chunk(chunk)
                if piece:
                    yield _wire(WireText(delta=piece))
                else:
                    # Tool-argument deltas (e.g. a large generate_report payload)
                    # carry no display text — emit a bare-newline keepalive so the
                    # streaming connection never goes idle during the long quiet
                    # stretch while the model writes the report. The frontend NDJSON
                    # parser skips empty lines, so this renders nothing.
                    yield b"\n"

            elif kind == "on_tool_start":
                name = event.get("name", "")
                inp = event["data"].get("input") or {}
                run_id = str(event.get("run_id") or uuid.uuid4())
                if run_id in seen_tool_calls:
                    continue
                seen_tool_calls.add(run_id)
                yield _wire(WireToolCall(id=run_id, name=name, args=_safe(inp)))

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


@router.post("/api/chat")
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
