"""Drilling & Project agent — pure RAG over FY 25-26 drilling + workover.

Reads the target-vs-actual annexures and lets the LLM surface where OIL is
over- or under-delivering. No Python scoring logic; the LLM compares the
target/actual columns in the retrieved tables.
"""
from __future__ import annotations

from ..core import signals
from .rag import llm_scan


AGENT = "drilling"


SYSTEM_PROMPT_TAIL = """You are the Drilling & Project agent inside the
Atlas intelligence OS for Oil India Limited.

Your scope:
- Exploratory drilling — Assam & AP, Rajasthan, NELP, OALP (meterage + wells)
- Development drilling — same regions, against the FY 25-26 BE
- Seismic surveys (2D LKM, 3D SQKM)
- Workover counts

For the morning brief, you want to flag:
- The dominant geography that is OVER target (exploratory)
- The dominant geography that is UNDER target (development), with the
  exact wells-behind-plan number — that's often the CXO-relevant signal
- Skip tiny rows where % achievement is meaningless (target wells < 5)
"""


def scan() -> list[signals.Signal]:
    return llm_scan(
        agent=AGENT,
        role=SYSTEM_PROMPT_TAIL,
        queries=[
            "OIL exploratory drilling target actual FY 2025-26 Assam Rajasthan",
            "OIL development drilling target actual FY 2025-26 meterage wells",
            "OIL drilling performance behind plan wells short",
            "OIL workover operations OGPS Rajasthan year-wise",
            # Strategic 100-well target / multi-year drilling plan
            "OIL 100 wells annual drilling plan capex annual report",
        ],
    )
