"""Andaman frontier-discovery facts for the Exploration scenario module.

The official filings on oil-india.com are the *system of record*. This
module makes a best-effort live scrape of OIL's press-release / archive
pages looking for Vijayapuram / Andaman references and records any
matching source URLs. The hard-coded ``ANDAMAN_FACTS`` (the figures
confirmed in the exchange disclosures) are the authoritative fallback so
the scenario module always renders — and so that, per the demo
guardrails, no volume is ever invented: there is no published reserve
estimate, and every downstream number is explicitly hypothetical.

Cached for the lifetime of the process (TTL-guarded) so the dashboard
never blocks on the network.
"""
from __future__ import annotations

import re
import time

from loguru import logger

_TTL_SECS = 60 * 60 * 6
_CACHE: dict[str, tuple[float, dict]] = {}

_SOURCE_PAGES = [
    "https://www.oil-india.com/press-release",
    "https://www.oil-india.com/archive-press-release",
]
_PATTERN = re.compile(r"(?i)vijayapuram|andaman")


# Confirmed from the exchange disclosures (system of record). No reserve
# estimate has been published; nothing here is booked into 2P.
ANDAMAN_FACTS = {
    "block": "Andaman offshore (East Andaman)",
    "wells": [
        {
            "well": "Vijayapuram-1",
            "date": "2024",
            "result": "dry",
            "gas_bearing": False,
            "note": "First well in the basin — non-commercial.",
        },
        {
            "well": "Vijayapuram-2",
            "date": "2025-09",
            "result": "gas discovery",
            "gas_bearing": True,
            "offshore_km": 17,
            "water_depth_m": 295,
            "methane_pct": 87,
            "note": "First gas in the basin; samples 87% methane; stock +3% on announcement.",
        },
        {
            "well": "Vijayapuram-3",
            "date": "2026-06",
            "result": "gas discovery",
            "gas_bearing": True,
            "offshore_km": 15,
            "water_depth_m": 355,
            "test_note": "continuous flaring on test at 1,900 m+",
            "gas_bearing_flag": True,
            "note": "Second basin discovery; 2 of 3 wells gas-bearing.",
        },
    ],
    "wells_drilled": 3,
    "wells_gas_bearing": 2,
    "reserve_estimate_published": False,
    "booked_in_2p": False,
    "capex_plan_note": "Backed by OIL's stated ₹1.3-trillion capex-by-2030 deepwater plan.",
    "timeline": [
        {"stage": "Vijayapuram-2 discovery", "when": "Sep 2025", "done": True},
        {"stage": "Vijayapuram-3 discovery", "when": "Jun 2026", "done": True},
        {"stage": "Appraisal", "when": "next", "done": False},
        {"stage": "FID", "when": "—", "done": False},
        {"stage": "First gas", "when": "FY32+ (frontier norm 7–10 yrs)", "done": False},
    ],
    "next_update_trigger": "Vijayapuram-4 spud",
}


def _scrape_sources() -> list[str]:
    """Best-effort: return any oil-india.com URLs whose page text or
    links reference Vijayapuram / Andaman. Never raises."""
    found: list[str] = []
    try:
        import httpx
    except Exception:  # noqa: BLE001
        return found
    headers = {"User-Agent": "Mozilla/5.0 (compatible; STRATA/1.0)"}
    for url in _SOURCE_PAGES:
        try:
            r = httpx.get(url, headers=headers, timeout=8.0, follow_redirects=True)
            if r.status_code != 200:
                continue
            text = r.text
            if _PATTERN.search(text):
                # collect the specific document links that mention it
                for href in re.findall(r'href="([^"]+\.pdf[^"]*)"', text, re.I):
                    seg = href.lower()
                    if _PATTERN.search(seg):
                        full = href if href.startswith("http") else "https://www.oil-india.com" + href
                        found.append(full)
                found.append(url)  # the index page itself matched
        except Exception as exc:  # noqa: BLE001
            logger.info(f"[andaman] scrape {url} skipped: {exc}")
            continue
    # de-dup, preserve order
    seen, out = set(), []
    for u in found:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def get_andaman() -> dict:
    """Andaman facts + live-scrape provenance, cached."""
    now = time.time()
    hit = _CACHE.get("andaman")
    if hit and (now - hit[0]) < _TTL_SECS:
        return hit[1]

    sources = _scrape_sources()
    payload = dict(ANDAMAN_FACTS)
    payload["live_sources"] = sources
    payload["scrape_status"] = (
        f"{len(sources)} live reference(s) found on oil-india.com"
        if sources else
        "no live match — using confirmed exchange-disclosure facts"
    )
    payload["system_of_record"] = "oil-india.com exchange disclosures"
    _CACHE["andaman"] = (now, payload)
    return payload


def reset_cache() -> None:
    _CACHE.clear()
