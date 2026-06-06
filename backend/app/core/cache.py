"""Disk-backed LLM cache so the demo never hangs on a stage.

For any call we wrap, the cache stores the final text + tool trace keyed by a
prompt-hash. Behaviour:

  - First time a prompt is seen: live call, then store.
  - Subsequent times: stream the cached result instantly, AND fire a live
    refresh in the background so the cache stays warm.
  - Curated entries (rehearsed prompts) can be hand-written into the override
    JSON file; those *never* get overwritten by background refresh.

The cache is intentionally simple — JSON files keyed by SHA1, no TTL, no LRU.
For a demo with O(100) distinct prompts the disk footprint is trivial.
"""
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, asdict, field
from pathlib import Path

from ..config import settings


CACHE_DIR = settings.chroma_dir.parent / "atlas_cache"
OVERRIDES_FILE = settings.chroma_dir.parent / "atlas_cache_overrides.json"


@dataclass
class CachedResponse:
    """The flattened result of one chat run. Stored verbatim; replayed as a
    stream of WireText events when served from cache."""
    text: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)  # parallel to tool_calls
    citations: list[dict] = field(default_factory=list)

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, d: dict) -> "CachedResponse":
        return cls(
            text=d.get("text", ""),
            tool_calls=d.get("tool_calls", []),
            tool_results=d.get("tool_results", []),
            citations=d.get("citations", []),
        )


def _key(model: str, prompt: str, scope: str = "chat") -> str:
    raw = f"{scope}::{model}::{prompt}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


def _path(key: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{key}.json"


# ---------- overrides (rehearsed prompts) ----------

_overrides_lock = threading.Lock()
_overrides_cache: dict[str, dict] | None = None
_overrides_mtime: float = 0.0


def _load_overrides() -> dict[str, dict]:
    """Read the overrides file. Reloaded on mtime change so editing the file
    during a demo doesn't require a restart."""
    global _overrides_cache, _overrides_mtime
    if not OVERRIDES_FILE.exists():
        return {}
    mtime = OVERRIDES_FILE.stat().st_mtime
    with _overrides_lock:
        if _overrides_cache is not None and mtime == _overrides_mtime:
            return _overrides_cache
        try:
            data = json.loads(OVERRIDES_FILE.read_text())
            assert isinstance(data, dict)
            _overrides_cache = data
            _overrides_mtime = mtime
        except Exception as e:
            print(f"[cache] failed to read overrides: {e}")
            _overrides_cache = {}
        return _overrides_cache


def get_override(model: str, prompt: str, scope: str = "chat") -> CachedResponse | None:
    ov = _load_overrides()
    entry = ov.get(_key(model, prompt, scope)) or ov.get(prompt.strip())
    if entry:
        return CachedResponse.from_json(entry)
    return None


# ---------- normal cache ----------

def get(model: str, prompt: str, scope: str = "chat") -> CachedResponse | None:
    override = get_override(model, prompt, scope)
    if override is not None:
        return override
    p = _path(_key(model, prompt, scope))
    if not p.exists():
        return None
    try:
        return CachedResponse.from_json(json.loads(p.read_text()))
    except Exception:
        return None


def put(model: str, prompt: str, response: CachedResponse, scope: str = "chat") -> None:
    """Store, but never clobber an override entry."""
    if get_override(model, prompt, scope) is not None:
        return
    p = _path(_key(model, prompt, scope))
    p.write_text(json.dumps(response.to_json(), indent=2))


def has(model: str, prompt: str, scope: str = "chat") -> bool:
    return get(model, prompt, scope) is not None
