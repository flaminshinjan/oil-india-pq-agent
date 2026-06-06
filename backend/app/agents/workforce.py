"""Workforce agent — pure RAG over synthetic HR feed + HR-related PQ context.

Retrieval surfaces the headcount/attrition table from Chroma; the LLM
identifies the worst-offender function vs the 5-year baseline.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..config import settings
from ..core import signals
from .rag import llm_scan


AGENT = "workforce"


SYSTEM_PROMPT_TAIL = """You are the Workforce agent inside the Atlas
intelligence OS for Oil India Limited.

Scope (synthetic baseline + OIL HR policy):
- Headcount by function / location
- TTM attrition by function vs the OIL 5-year baseline
- Open requisitions, time-to-fill
- HR policy Q&A from indexed policy documents — always cite the policy
  clause/section you used

Read-only. Never simulate an approval, posting, or transfer.

For the morning brief:
- Lead with the function whose TTM attrition is most above baseline,
  with the exact delta in percentage points
- Roll up total open reqs if it's a useful side signal
"""


def _live_state_block() -> str:
    p = Path(settings.runtime_data_dir) / "synthetic" / "workforce.json"
    if not p.exists():
        return ""
    try:
        data = json.loads(p.read_text())
    except Exception:
        return ""
    return "Current workforce baseline + by-function snapshot:\n```json\n" + json.dumps(data, indent=2) + "\n```"


def scan() -> list[signals.Signal]:
    return llm_scan(
        agent=AGENT,
        role=SYSTEM_PROMPT_TAIL,
        queries=[
            "OIL recruitment attrition headcount vacancies engineering",
            "OIL HR policy PSU posts ministry petroleum",
        ],
        extra_context=_live_state_block(),
    )
