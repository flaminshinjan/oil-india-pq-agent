"""Procurement agent — pure RAG over the synthetic PR + bids feed.

The procurement JSON is in Chroma; retrieval surfaces the PR, the weighting
criteria, and the inbound bids. The LLM scores and recommends — Atlas
itself does no scoring math.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..config import settings
from ..core import signals
from .rag import llm_scan


AGENT = "procurement"


SYSTEM_PROMPT_TAIL = """You are the Procurement agent inside the Atlas
intelligence OS for Oil India Limited.

Scope (synthetic + read-only):
- Drafting RFP packages from a purchase request
- Scoring inbound bids against the PR's weighted criteria (price,
  delivery, OEM rating, warranty, compliance)
- Flagging clause deviations vs. OIL's standard contract template
- Recommending a winner with a written rationale

Your output is advisory — a recommendation a buyer reviews and approves
outside Atlas. Never simulate an action.

When you compose the recommendation:
- Compute the weighted score yourself from the criteria_weights and the
  individual bid fields (price, delivery, OEM rating, warranty, deviations).
- Surface any high-severity clause deviations explicitly.
- State the runner-up + why, in case the winner's deviations don't clear.
"""


def _live_state_block() -> str:
    """Hand the LLM the current PR + bids as a clean JSON block so it can
    score without prompt parsing tricks."""
    p = Path(settings.runtime_data_dir) / "synthetic" / "procurement.json"
    if not p.exists():
        return ""
    try:
        data = json.loads(p.read_text())
    except Exception:
        return ""
    return "Current open RFP package:\n```json\n" + json.dumps(data, indent=2) + "\n```"


def scan() -> list[signals.Signal]:
    return llm_scan(
        agent=AGENT,
        role=SYSTEM_PROMPT_TAIL,
        queries=[
            "OIL procurement RFP bid scoring weighting criteria",
            "OIL contract liability clause OEM warranty",
        ],
        extra_context=_live_state_block(),
    )
