"""Production & Reserves agent.

Pure RAG: retrieves the 10-year production/reserves data + relevant PQ
excerpts and asks the LLM what's worth surfacing. No Python-side analytics
— the LLM reads the actual tables (including the full RRR + 2P reserves
series) and decides which signal a CXO needs.
"""
from __future__ import annotations

from ..core import signals
from .rag import llm_scan


AGENT = "production"


SYSTEM_PROMPT_TAIL = """You are the Production & Reserves agent inside the
Atlas intelligence OS for Oil India Limited.

Your scope:
- Crude oil production (MMT), natural gas production (MMSCM)
- 2P reserves (oil MMT, gas BCM, total MMToE)
- Reserve Replacement Ratio (RRR) and reserve accretion
- Year-wise trends and state-wise breakdowns where available

For a CXO morning brief, you typically want to flag:
- RRR below 1.0 (or trending toward it) over multiple FYs
- 2P oil reserve decline year-on-year
- Production milestones or unexpected reversals
Quote the exact figures from the retrieved tables — don't round or paraphrase.
"""


def scan() -> list[signals.Signal]:
    return llm_scan(
        agent=AGENT,
        role=SYSTEM_PROMPT_TAIL,
        queries=[
            "OIL crude oil production year-wise FY 2020-21 to 2025-26 MMT trend",
            "OIL 2P oil reserves year-wise MMT decline",
            "OIL Reserve Replacement Ratio RRR by FY",
            "OIL natural gas production trend MMSCM",
            # Strategic context from annual reports / BRSR
            "OIL strategic target 4 MMT crude oil 5 BCM natural gas",
            "OIL chairman vision production roadmap annual report",
        ],
    )
