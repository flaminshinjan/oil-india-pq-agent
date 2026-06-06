"""Pydantic types for the chat API + the wire protocol used in streaming."""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


# ---- Streaming wire types ----
# The server streams a sequence of JSON objects (one per line). Each has a
# `type` field; the frontend renders each type differently.

class WireBase(BaseModel):
    type: str


class WireText(WireBase):
    type: Literal["text"] = "text"
    delta: str  # token / chunk of assistant text


class WireToolCall(WireBase):
    type: Literal["tool_call"] = "tool_call"
    id: str
    name: str
    args: dict


class WireToolResult(WireBase):
    type: Literal["tool_result"] = "tool_result"
    id: str
    name: str
    result: dict


class WireDone(WireBase):
    type: Literal["done"] = "done"
    citations: list[dict] = []


class WireError(WireBase):
    type: Literal["error"] = "error"
    message: str
