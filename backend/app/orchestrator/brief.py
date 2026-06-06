"""Orchestrator — turn agent signals into the CXO morning brief.

Two stages:

  1. `refresh_signals()` — run every agent's scan() in parallel; each
     emits 1–3 signals into the shared SQLite store via RAG over Chroma.

  2. `build_brief()` — read the ranked signals, then ask the LLM to
     compose the headline narrative across them. The LLM looks for the
     cross-domain insight (e.g. fusing Production-RRR with Drilling-gap)
     and writes the 2–3 paragraph headline a CXO sees on load.

Both stages cache LLM calls keyed by the prompt — repeated refreshes
against the same data return instantly.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import re
import time
from dataclasses import dataclass

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from ..agents import DOMAIN_AGENTS
from ..config import settings
from ..core import cache, signals
from ..core.prompts import date_block


# ------------------------------------------------------------------
# Refresh
# ------------------------------------------------------------------

def refresh_signals() -> None:
    """Re-run every agent's scan() in parallel."""
    with cf.ThreadPoolExecutor(max_workers=len(DOMAIN_AGENTS)) as ex:
        futs = {
            name: ex.submit(getattr(mod, "scan", lambda: []))
            for name, mod in DOMAIN_AGENTS.items()
        }
        for name, fut in futs.items():
            try:
                fut.result()
            except Exception as e:
                print(f"[orchestrator] agent {name} scan failed: {e}")


# ------------------------------------------------------------------
# Headline composition (LLM-driven)
# ------------------------------------------------------------------

HEADLINE_SYSTEM = """You are the CXO copilot inside Atlas, an advisory
intelligence OS for Oil India Limited. Below are the open signals each
domain agent has published from their latest scan of OIL's data.

Your job: compose **the morning brief headline** — what most needs the
CXO's attention right now, ideally an insight that *cuts across two or
more agents* (e.g., a Production signal that explains a Drilling gap).

# Output contract — STRICT
Return a single JSON object — no prose, no code fences:

{
  "title":  string (<= 110 chars, no markdown, the punchline of the insight),
  "body":   string (2 to 4 short paragraphs, may use **bold** for key
                    numbers, MUST quote exact figures from the signal bodies),
  "severity": "high" | "critical" | "med",
  "refs":   [ { "filename": "...", "section": "..." } ]
              — pulled from the signals you used, 1–4 entries,
  "linked_signal_ids": [int, ...]   — ids of the signals you wove together
}

Rules:
- Prefer a CROSS-DOMAIN insight if two signals naturally connect (e.g.,
  production decline + drilling-execution gap). If no cross-link exists,
  pick the single highest-impact signal and write the headline about it.
- Quote numbers exactly as in the signal bodies.
- Don't invent data. If the signals don't contain a number you need,
  don't include the number.
"""


def _llm():
    return ChatAnthropic(
        model=settings.anthropic_model,
        anthropic_api_key=settings.anthropic_api_key,
        temperature=0,
        max_tokens=2048,
    )


def _signals_for_prompt(sigs: list[dict]) -> str:
    bits = []
    for s in sigs:
        bits.append(
            f"--- signal id={s.get('id')} agent={s.get('agent')} "
            f"severity={s.get('severity')} ---\n"
            f"title: {s.get('title')}\n"
            f"body:  {s.get('body')}\n"
            f"refs:  {json.dumps(s.get('refs') or [], ensure_ascii=False)}"
        )
    return "\n\n".join(bits)


def _parse_headline_json(text: str) -> dict | None:
    text = text.strip()
    candidates: list[str] = []
    candidates.append(text)
    m = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if m:
        candidates.insert(0, m.group(1).strip())
    s, e = text.find("{"), text.rfind("}")
    if s >= 0 and e > s:
        candidates.append(text[s : e + 1])
    for c in candidates:
        try:
            v = json.loads(c)
            if isinstance(v, dict) and v.get("title") and v.get("body"):
                return v
        except json.JSONDecodeError:
            continue
    return None


def compose_headline(sig_dicts: list[dict]) -> dict:
    """LLM-composed headline from the open signals."""
    if not sig_dicts:
        return {
            "title": "Atlas is ready",
            "body": "No signals yet — run a refresh, or start a copilot conversation.",
            "severity": "info",
            "refs": [],
            "linked_signal_ids": [],
        }

    system = HEADLINE_SYSTEM + "\n\n" + date_block()
    user = (
        "# Open signals from this scan\n\n"
        + _signals_for_prompt(sig_dicts)
        + "\n\nNow emit the JSON headline object."
    )
    prompt_key = system + "\n----\n" + user

    cached = cache.get(settings.anthropic_model, prompt_key, scope="headline")
    if cached and cached.text:
        v = _parse_headline_json(cached.text)
        if v:
            return _shape(v, sig_dicts)

    try:
        resp = _llm().invoke([SystemMessage(content=system), HumanMessage(content=user)])
        text = resp.content if isinstance(resp.content, str) else "".join(
            (b.get("text", "") if isinstance(b, dict) else str(b)) for b in resp.content
        )
    except Exception as e:
        print(f"[orchestrator] headline LLM failed: {e}")
        # Fallback: highest-severity signal as the headline.
        return _highest_severity_fallback(sig_dicts)

    cache.put(
        settings.anthropic_model,
        prompt_key,
        cache.CachedResponse(text=text),
        scope="headline",
    )

    v = _parse_headline_json(text)
    if not v:
        return _highest_severity_fallback(sig_dicts)
    return _shape(v, sig_dicts)


def _shape(v: dict, sig_dicts: list[dict]) -> dict:
    """Ensure the headline dict has all expected fields, with a metric block
    derived from the linked signals so the UI can render structured numbers."""
    linked_ids = v.get("linked_signal_ids") or []
    linked = [s for s in sig_dicts if s.get("id") in linked_ids]
    # If the LLM linked to production + drilling, build a cross_domain metric
    metric = None
    prod = next(
        (s for s in linked if s.get("agent") == "production"
         and (s.get("metric") or {}).get("kind") == "rrr_trend"),
        None,
    )
    drill = next(
        (s for s in linked if s.get("agent") == "drilling"
         and (s.get("metric") or {}).get("kind") == "drilling_gap"),
        None,
    )
    if prod and drill:
        metric = {
            "kind": "cross_domain",
            "production": prod["metric"],
            "drilling": drill["metric"],
        }
    return {
        "title": v.get("title", "")[:160],
        "body": v.get("body", ""),
        "severity": v.get("severity") or "high",
        "refs": v.get("refs") or [],
        "metric": metric,
        "linked_signal_ids": linked_ids,
    }


def _highest_severity_fallback(sig_dicts: list[dict]) -> dict:
    rank = {"critical": 4, "high": 3, "med": 2, "low": 1, "info": 0}
    top = sorted(sig_dicts, key=lambda s: (-rank.get(s["severity"], 0), -s["ts"]))[0]
    return {
        "title": top["title"],
        "body": top["body"],
        "severity": top["severity"],
        "refs": top.get("refs") or [],
        "metric": top.get("metric"),
        "linked_signal_ids": [top.get("id")],
    }


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

@dataclass
class MorningBrief:
    headline: dict
    signals: list[dict]
    refreshed_at: float


def build_brief(*, refresh: bool = True, limit: int = 8) -> MorningBrief:
    if refresh:
        refresh_signals()
    ranked = [s.to_dict() for s in signals.list_ranked(limit=limit)]
    headline = compose_headline(ranked)
    return MorningBrief(headline=headline, signals=ranked, refreshed_at=time.time())


def brief_to_dict(b: MorningBrief) -> dict:
    return {
        "headline": b.headline,
        "signals": b.signals,
        "refreshed_at": b.refreshed_at,
    }
