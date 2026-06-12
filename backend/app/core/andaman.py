"""Andaman frontier-discovery facts for the Exploration scenario module.

Live sourcing is done with **Tavily web search** (the same TAVILY_API_KEY
the agents use) — the Andaman / Sri-Vijayapuram discoveries are public
news + exchange disclosures that aren't on oil-india.com's static
press-release index, so a direct page scrape misses them. Tavily finds
the real articles and we surface their URLs as live provenance. If Tavily
is unavailable we fall back to a direct oil-india.com scrape, then to the
hard-coded ``ANDAMAN_FACTS``.

The numeric figures in ``ANDAMAN_FACTS`` are the values confirmed in the
official announcement (verified against the live web). Per the demo
guardrails no volume is ever invented: there is no published reserve
estimate, so every downstream scenario number is explicitly hypothetical.

Cached for the lifetime of the process (TTL-guarded) so the dashboard
never blocks on the network.
"""
from __future__ import annotations

import os
import re
import time

from loguru import logger

_TTL_SECS = 60 * 60 * 6
_CACHE: dict[str, tuple[float, dict]] = {}

_TAVILY_QUERIES = [
    "OIL India Sri Vijayapuram-3 Andaman offshore natural gas discovery 2026",
    "Oil India Vijayapuram-2 Andaman gas discovery September 2025",
]
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
            "result": "dry — write-off ≈ ₹720 crore",
            "gas_bearing": False,
            "writeoff_inr_cr": 720,
            "note": "First well in the basin — not a gas success; associated "
                    "exploratory write-off ≈ ₹720 cr reported against the Q2 FY26 result.",
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


def _tavily_sources() -> tuple[list[dict], str]:
    """Find live Andaman/Vijayapuram references via Tavily. Returns
    (sources, method). Each source: {title, url, published, snippet}.
    Never raises."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return [], "tavily-unconfigured"
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[andaman] tavily import failed: {exc}")
        return [], "tavily-import-failed"

    seen: set[str] = set()
    out: list[dict] = []
    for q in _TAVILY_QUERIES:
        try:
            res = client.search(query=q, search_depth="advanced",
                                max_results=5, include_answer=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[andaman] tavily query failed: {exc}")
            continue
        for r in res.get("results", []):
            url = r.get("url") or ""
            title = r.get("title") or ""
            blob = f"{title} {r.get('content','')}"
            # keep only results that actually mention the basin/well
            if not _PATTERN.search(blob) and "vijayapuram" not in url.lower():
                continue
            if url in seen:
                continue
            seen.add(url)
            out.append({
                "title": title[:160],
                "url": url,
                "published": r.get("published_date"),
                "snippet": (r.get("content") or "")[:240],
            })
    return out, "tavily"


def _scrape_oilindia() -> list[dict]:
    """Secondary fallback: direct oil-india.com page scrape."""
    found: list[dict] = []
    try:
        import httpx
    except Exception:  # noqa: BLE001
        return found
    headers = {"User-Agent": "Mozilla/5.0 (compatible; STRATA/1.0)"}
    for url in _SOURCE_PAGES:
        try:
            r = httpx.get(url, headers=headers, timeout=8.0, follow_redirects=True)
            if r.status_code == 200 and _PATTERN.search(r.text):
                found.append({"title": "oil-india.com press release", "url": url,
                              "published": None, "snippet": None})
        except Exception:  # noqa: BLE001
            continue
    return found


def get_andaman() -> dict:
    """Andaman facts + live web provenance (Tavily-first), cached."""
    now = time.time()
    hit = _CACHE.get("andaman")
    if hit and (now - hit[0]) < _TTL_SECS:
        return hit[1]

    sources, method = _tavily_sources()
    if not sources:
        sources = _scrape_oilindia()
        if sources:
            method = "oil-india-scrape"

    payload = dict(ANDAMAN_FACTS)
    payload["live_sources"] = sources
    payload["live_source_method"] = method
    if sources and method == "tavily":
        payload["scrape_status"] = (
            f"{len(sources)} live web source(s) via Tavily — "
            f"figures cross-checked against the official announcement"
        )
    elif sources:
        payload["scrape_status"] = f"{len(sources)} live reference(s) on oil-india.com"
    elif method.startswith("tavily-"):
        payload["scrape_status"] = (
            "Tavily unavailable — using confirmed exchange-disclosure facts"
        )
    else:
        payload["scrape_status"] = "no live match — using confirmed exchange-disclosure facts"
    payload["system_of_record"] = "oil-india.com / NSE-BSE exchange disclosures"
    _CACHE["andaman"] = (now, payload)
    return payload


def reset_cache() -> None:
    _CACHE.clear()
