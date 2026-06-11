"""HSE agent — pure RAG over OIL's BRSR / ESG / Annual Reports.

No synthetic CV / PPE feed any more. Signals are generated from the real
safety disclosures in the corpus + the BRSR-extracted LTIFR table.
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

Your scope, sourced ENTIRELY from OIL's BRSR / ESG / Annual Reports:
- Lost-Time Injury Frequency Rate (LTIFR), per million person-hours
- Fatalities and high-consequence injuries
- Recordable injuries (workers and executives)
- HSE management system framework + 5-Star Work-Environment ratings
- Stop-Work-Authority, near-miss culture, audits

Atlas is advisory: name the metric, the FY it covers, the source
document. Never invent counts. Use the BRSR-extracted LTIFR values
(workers: 0.071 FY24-25, 0.158 FY23-24, 0.462 FY22-23) and surface
the year-on-year improvement narrative.

Do NOT reference any "live CV PPE feed" — that feed has been retired.
"""


def _live_state_block() -> str:
    """LTIFR + incident snapshot from disclosures (no synthetic feed)."""
    p = Path(settings.runtime_data_dir) / "disclosures" / "safety_hr.json"
    if not p.exists():
        return ""
    try:
        data = json.loads(p.read_text())
    except Exception:
        return ""

    now = datetime.now(IST)
    lines = [f"Current time (IST): **{now.strftime('%a %d %b %Y, %H:%M')}**", ""]
    rows = data.get("ltifr_5yr") or []
    if rows:
        lines.append("Worker LTIFR per million person-hours (BRSR):")
        for r in rows:
            workers = r.get("workers")
            execs = r.get("executives")
            lines.append(
                f"- FY{r.get('fy')}: workers "
                + (f"{workers:.3f}" if workers is not None else "—")
                + ", executives "
                + (f"{execs:.3f}" if execs is not None else "—")
            )
    inc = data.get("incidents_3yr") or []
    if inc:
        lines.append("")
        lines.append("Recordable / high-consequence / fatalities (workers):")
        for r in inc:
            lines.append(
                f"- FY{r.get('fy')}: recordable {r.get('recordable_workers',0)}, "
                f"high-consequence {r.get('high_consequence_workers',0)}, "
                f"fatalities {r.get('fatalities_workers',0)}"
            )
    heads = data.get("headlines_fy25") or []
    if heads:
        lines.append("")
        lines.append("BRSR FY24-25 headlines:")
        for h in heads:
            lines.append(f"- {h}")
    return "\n".join(lines)


def scan() -> list[signals.Signal]:
    return llm_scan(
        agent=AGENT,
        role=SYSTEM_PROMPT_TAIL,
        queries=[
            "OIL LTIFR lost time injury frequency rate BRSR workers",
            "OIL safety performance fatalities total recordable incident",
            "OIL HSE management system 5-star work environment rating",
            "OIL safety stop work authority near miss reporting",
        ],
        extra_context=_live_state_block(),
    )
