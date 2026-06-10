"""/api/sources/* — serve OIL's annual / BRSR / ESG / 10-yr PDFs so the
citation pills can open the actual document inline.

  GET /api/sources/list           list all available source files
  GET /api/sources/file/<name>    serve one file (inline, browser PDF viewer)

Files live in /app/sources/ in the container (mounted via Dockerfile).
Path traversal is blocked — only files whose resolved path is inside the
sources directory are served.
"""
from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse


router = APIRouter(prefix="/api/sources")


_BASE = Path(__file__).resolve().parents[2]
SOURCES_DIRS = [
    _BASE / "sources",          # bundled PDFs
    _BASE / "data" / "db",      # docx + xlsx the chat agent indexed
    _BASE / "data" / "DB",      # macOS-case fallback
    _BASE / "data" / "synthetic",
]


def _find(name: str) -> Path | None:
    """Search every known source directory for a filename, path-traversal-safe."""
    for d in SOURCES_DIRS:
        if not d.exists():
            continue
        candidate = (d / name).resolve()
        try:
            candidate.relative_to(d.resolve())
        except ValueError:
            continue
        if candidate.is_file():
            return candidate
    return None


@router.get("/list")
async def list_sources():
    """Available source files across every search dir."""
    items: list[dict] = []
    seen: set[str] = set()
    for d in SOURCES_DIRS:
        if not d.exists():
            continue
        for p in sorted(d.iterdir()):
            if not p.is_file() or p.name in seen:
                continue
            seen.add(p.name)
            items.append({
                "filename": p.name,
                "size_bytes": p.stat().st_size,
                "mime": mimetypes.guess_type(p.name)[0] or "application/octet-stream",
            })
    return {"sources": items, "count": len(items)}


@router.head("/file/{name:path}")
@router.get("/file/{name:path}")
async def get_source(name: str):
    """Serve one source file by filename, regardless of which directory
    it lives in. Path-traversal-safe (only files inside one of the
    declared search dirs are returned)."""
    candidate = _find(name)
    if not candidate:
        raise HTTPException(404, f"source not found: {name}")
    mime = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
    return FileResponse(
        candidate,
        media_type=mime,
        headers={"Content-Disposition": f'inline; filename="{candidate.name}"'},
    )
