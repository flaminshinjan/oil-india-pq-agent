"""HSE agent — pure RAG over PPE feed + safety PQ context.

The synthetic PPE feed is in Chroma (ingested from data/synthetic/ppe_events.json),
so retrieval surfaces the recent events. We additionally hand the LLM a
freshly-computed "now" block so it can render relative times ("9 min ago")
against the actual wall clock at scan time, not against a stale ingestion.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ..config import settings
from ..core import signals
from .rag import llm_scan


AGENT = "hse"

IST = ZoneInfo("Asia/Kolkata")


SYSTEM_PROMPT_TAIL = """You are the HSE agent inside the Atlas intelligence
OS for Oil India Limited.

Your scope:
- PPE compliance events (hard-hat, hi-vis, gloves) detected by the live
  CV pipeline at field sites
- Hazard / near-miss reporting
- Cross-link safety flags to assets / projects in other agents' scope

Atlas is advisory: name the site, the time, the type, propose a next step,
but never auto-action anything. Use **N min ago / Nh Mm ago** relative
times (computed against the current time block provided), not raw
timestamps.
"""


def _live_state_block() -> str:
    """Render the freshest PPE events with timestamps relative to *now*."""
    p = Path(settings.runtime_data_dir) / "synthetic" / "ppe_events.json"
    if not p.exists():
        return ""
    try:
        data = json.loads(p.read_text())
    except Exception:
        return ""

    now = datetime.now(IST)
    lines = [f"Current time (IST): **{now.strftime('%a %d %b %Y, %H:%M')}**", ""]
    lines.append("Recent PPE events (sorted newest first):")
    for ev in sorted(data.get("events", []), key=lambda e: e.get("minutes_ago", 0)):
        mins = int(ev.get("minutes_ago", 0))
        if mins < 60:
            rel = f"{mins} min ago"
        elif mins < 24 * 60:
            rel = f"{mins // 60}h {mins % 60}m ago"
        else:
            rel = f"{mins // 1440}d ago"
        lines.append(
            f"- {rel} · site: {ev.get('site','?')} · asset: {ev.get('asset','?')} "
            f"· type: {ev.get('type','?')} · confidence: {ev.get('confidence',0)} "
            f"· shift: {ev.get('shift','?')} · crew lead: {ev.get('crew_lead','—')}"
        )
    notes = data.get("site_notes") or {}
    if notes:
        lines.append("")
        lines.append("Site notes:")
        for site, note in notes.items():
            lines.append(f"- {site}: {note}")
    return "\n".join(lines)


def scan() -> list[signals.Signal]:
    return llm_scan(
        agent=AGENT,
        role=SYSTEM_PROMPT_TAIL,
        queries=[
            "OIL safety PPE compliance hard-hat incidents",
            "OIL HSE policy near miss reporting",
        ],
        extra_context=_live_state_block(),
    )
