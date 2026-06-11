"""Procurement agent — pure RAG over OIL's procurement disclosures.

No synthetic PR bid walk-through any more. Signals are drawn from the
Annual Reports + BRSR (MSE share, GeM portal procurement, vendor
development), and from PQ replies on procurement policy.
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

Your scope (read-only, sourced from OIL's Annual Reports + BRSR + PQ
replies):
- MSE / SC-ST / Women-entrepreneur procurement (Public Procurement
  Policy compliance, 25 % MSE floor)
- GeM portal procurement value, year-on-year
- Make-in-India / Class-I local supplier preference
- Vendor-development programmes (NE region MSME outreach)

Atlas is advisory. Cite the Annual Report or BRSR section, name the FY,
state the figure. Never invent vendor names or bid values — OIL does not
publish live bid evaluations. The synthetic demo PR has been retired;
focus on the disclosed procurement metrics.
"""


def _live_state_block() -> str:
    """Hand the LLM the disclosed MSE + GeM rows so it can quote them
    accurately without hallucinating."""
    p = Path(settings.runtime_data_dir) / "disclosures" / "procurement.json"
    if not p.exists():
        return ""
    try:
        data = json.loads(p.read_text())
    except Exception:
        return ""
    return "OIL procurement disclosures (Annual Reports + BRSR):\n```json\n" + json.dumps(data, indent=2) + "\n```"


def scan() -> list[signals.Signal]:
    return llm_scan(
        agent=AGENT,
        role=SYSTEM_PROMPT_TAIL,
        queries=[
            "OIL MSE micro small enterprise procurement share BRSR",
            "OIL GeM portal procurement value annual report",
            "OIL vendor development MSME purchase preference policy",
            "OIL local supplier Make-in-India procurement",
        ],
        extra_context=_live_state_block(),
    )
