"""Tools exposed to the LangGraph agent.

The chat agent uses a strict 4-step source hierarchy when answering:

    1. `search_oil_data`              — DB/ Excel tables (production, drilling,
                                         workover, reserves, FY annexures).
                                         Most authoritative for numeric facts.
                                         Synthetic JSON feeds (workforce,
                                         procurement, PPE) are EXCLUDED so the
                                         chat never cites a made-up table.
    2. `search_parliamentary_replies` — Past Lok Sabha / Rajya Sabha PQ replies
                                         (most recent session preferred).
    3. `search_corporate_reports`     — Annual reports, BRSR, ESG Data Books.
    4. `search_web`                   — Tavily web search.  LAST RESORT.
                                         Results MUST be marked "from public
                                         web" in the answer.

Each search tool returns a small JSON-serialisable dict that the LLM can quote
back in its answer. Citations come back as `[file: <name>, section: <section>]`
or `[web: <title> — <url>]` so attribution is unambiguous.
"""
from __future__ import annotations

import os
from typing import Annotated, Any

from langchain_core.tools import tool
from loguru import logger

from ..retrieval.vectorstore import get_store


# Files in DB/ that are synthetic demo feeds, not OIL disclosures. The
# chat agent never cites these — dashboards may still surface them.
_SYNTHETIC_DB_FILES = {
    "workforce.json",
    "workforce.legacy.json",
    "procurement.json",
    "ppe_events.json",
    "safety_hr.json",
}


def _is_synthetic(hit) -> bool:
    md = hit.metadata or {}
    fn = (md.get("filename") or "").lower()
    return fn in {n.lower() for n in _SYNTHETIC_DB_FILES}


def _format_hit(hit) -> dict[str, Any]:
    md = hit.metadata or {}
    return {
        "source":   md.get("source", ""),
        "filename": md.get("filename", ""),
        "session":  md.get("session", ""),
        "kind":     md.get("kind", ""),
        "section":  md.get("section", ""),
        "score":    round(float(hit.score), 3),
        "excerpt":  hit.text,
        "sibling":  bool(md.get("sibling_of")),
    }


@tool
def search_oil_data(
    query: Annotated[str, "Natural-language search for numeric / FY-wise facts (production, drilling, reserves, performance)."],
    k:     Annotated[int, "Number of factual excerpts to retrieve (1–10)."] = 5,
) -> dict:
    """**STEP 1 — PREFERRED FIRST CALL.**  Searches OIL's structured DB
    tables: production, gas, reserves, RRR, wells, drilling, workover,
    and the FY 2025-26 performance annexures.

    Synthetic / placeholder JSON feeds are filtered out — every result
    you get back is from OIL's own ledger of operational disclosures.

    Use this for any numeric or trend claim. Only fall back to the
    other tools if this returns weak / no relevant hits (top score < ~0.45).
    """
    k = max(1, min(int(k or 5), 10))
    raw = get_store().search("db", query, k=k * 2, with_siblings=True, max_total=14)
    hits = [h for h in raw if not _is_synthetic(h)][:k]
    return {
        "query":    query,
        "count":    len(hits),
        "note":     "DB tables only — synthetic feeds excluded.",
        "results":  [_format_hit(h) for h in hits],
    }


@tool
def search_parliamentary_replies(
    query: Annotated[str, "Natural-language search across past parliamentary Q&A replies."],
    k:     Annotated[int, "Number of PQ excerpts to retrieve (1–10)."] = 5,
) -> dict:
    """**STEP 2 — try AFTER `search_oil_data`.**  Past Lok Sabha and
    Rajya Sabha question replies (Budget Session 2026 → previous sessions).
    Use for: precedent phrasing, qualitative initiatives, partnerships,
    CSR / recruitment / alternative-energy questions.

    Ranked so the most-recent session bubbles up first.
    """
    k = max(1, min(int(k or 5), 10))
    raw = get_store().search("pq", query, k=k * 2, with_siblings=True, max_total=14)
    pq_hits = [h for h in raw if (h.metadata or {}).get("source", "").startswith("PQs/")]
    # Boost recent sessions: session strings sort alphabetically with
    # "WINTER 2025" / "BUDGET SESSION 2026" near the top; we re-sort by
    # session descending then score.
    pq_hits.sort(key=lambda h: (
        -1 if "2026" in (h.metadata or {}).get("session", "") else 0,
        -1 if "winter" in (h.metadata or {}).get("session", "").lower() else 0,
        -float(h.score),
    ))
    pq_hits = pq_hits[:k]
    return {
        "query":   query,
        "count":   len(pq_hits),
        "note":    "Parliamentary replies only — most recent session first.",
        "results": [_format_hit(h) for h in pq_hits],
    }


@tool
def search_corporate_reports(
    query: Annotated[str, "Natural-language search across Annual Reports, BRSR and ESG Data Books."],
    k:     Annotated[int, "Number of excerpts to retrieve (1–10)."] = 5,
) -> dict:
    """**STEP 3 — try AFTER parliamentary replies.**  Annual Reports,
    BRSR (Business Responsibility & Sustainability) reports and ESG Data
    Books (FY 2020-21 → FY 2024-25). Use for: capex, sustainability
    metrics, LTIFR, governance, chairman-statement framing, diversity
    figures, training spend.

    The latest BRSR / ESG numbers supersede older PQ snapshots.
    """
    k = max(1, min(int(k or 5), 10))
    raw = get_store().search("pq", query, k=k * 2, with_siblings=True, max_total=14)
    corp_hits = [h for h in raw if not (h.metadata or {}).get("source", "").startswith("PQs/")]
    corp_hits = corp_hits[:k]
    return {
        "query":   query,
        "count":   len(corp_hits),
        "note":    "Annual reports / BRSR / ESG only.",
        "results": [_format_hit(h) for h in corp_hits],
    }


@tool
def search_web(
    query: Annotated[str, "Natural-language web search query."],
    k:     Annotated[int, "Number of web results to retrieve (1–5)."] = 4,
) -> dict:
    """**STEP 4 — LAST RESORT.**  Public web search via Tavily.  Use ONLY
    when steps 1-3 have failed to surface the fact (e.g. very recent
    industry news, third-party analysis, public-government releases not
    yet in the corpus).

    **Mandatory in your reply:** flag every web-sourced sentence with
    "(per public web; outside OIL's internal corpus)" and list the URL in
    the Sources block.  Web results are not authoritative for OIL's own
    numbers — prefer the internal sources whenever a conflict exists.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {
            "query":  query,
            "count":  0,
            "error":  "Tavily not configured — TAVILY_API_KEY env var missing.",
            "results": [],
        }

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        res = client.search(
            query=query,
            search_depth="basic",
            max_results=max(1, min(int(k or 4), 5)),
            include_answer=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[search_web] tavily failed: {exc}")
        return {
            "query": query,
            "count": 0,
            "error": f"tavily error: {exc}",
            "results": [],
        }

    items = []
    for r in res.get("results") or []:
        items.append({
            "title":   r.get("title"),
            "url":     r.get("url"),
            "snippet": (r.get("content") or "")[:400],
            "score":   r.get("score"),
            "kind":    "web",
        })

    return {
        "query":   query,
        "count":   len(items),
        "note":    "WEB RESULTS — outside OIL's internal corpus. Caveat them in the answer.",
        "results": items,
    }


@tool
def list_available_sources() -> dict:
    """Quick directory of corpus contents so the agent can say "I don't
    have data on X" with confidence instead of guessing."""
    store = get_store()
    groups: dict[str, set[str]] = {}
    for coll in (store.pq, store.db):
        try:
            res = coll.get(include=["metadatas"])
        except Exception:
            continue
        for m in res.get("metadatas") or []:
            if not m:
                continue
            src = m.get("source") or ""
            if not src:
                continue
            top = src.split("/", 1)[0]
            groups.setdefault(top, set()).add(src)
    out = {k: sorted(v) for k, v in groups.items()}
    return {"groups": out, "total_files": sum(len(v) for v in out.values())}


import ast as _ast
import math as _math


def _safe_eval(expr: str) -> float:
    """Evaluate an arithmetic expression with a hard whitelist — numbers,
    + - * / // % **, parentheses, unary +/-, and a few named helpers. No
    names, attributes, comprehensions, or builtins. Raises on anything else."""
    def _growth(curr, prior):
        if prior == 0:
            raise ValueError("growth from a zero base is undefined")
        return (curr - prior) / prior * 100.0

    def _cagr(end, start, years):
        if start <= 0 or years <= 0:
            raise ValueError("cagr needs positive start and years")
        return ((end / start) ** (1.0 / years) - 1.0) * 100.0

    def _pct(part, whole):
        if whole == 0:
            raise ValueError("percent of a zero whole is undefined")
        return part / whole * 100.0

    funcs = {
        "growth": _growth, "cagr": _cagr, "pct": _pct,
        "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
        "sqrt": _math.sqrt,
    }

    def _ev(node):
        if isinstance(node, _ast.Expression):
            return _ev(node.body)
        if isinstance(node, _ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("only numeric constants allowed")
        if isinstance(node, _ast.BinOp):
            l, r = _ev(node.left), _ev(node.right)
            op = node.op
            if isinstance(op, _ast.Add): return l + r
            if isinstance(op, _ast.Sub): return l - r
            if isinstance(op, _ast.Mult): return l * r
            if isinstance(op, _ast.Div): return l / r
            if isinstance(op, _ast.FloorDiv): return l // r
            if isinstance(op, _ast.Mod): return l % r
            if isinstance(op, _ast.Pow): return l ** r
            raise ValueError("operator not allowed")
        if isinstance(node, _ast.UnaryOp):
            v = _ev(node.operand)
            if isinstance(node.op, _ast.UAdd): return +v
            if isinstance(node.op, _ast.USub): return -v
            raise ValueError("unary operator not allowed")
        if isinstance(node, _ast.Call):
            if not isinstance(node.func, _ast.Name) or node.func.id not in funcs:
                raise ValueError("only growth/cagr/pct/abs/round/min/max/sum/sqrt allowed")
            args = [_ev(a) for a in node.args]
            return funcs[node.func.id](*args)
        if isinstance(node, (_ast.List, _ast.Tuple)):
            return [_ev(e) for e in node.elts]
        raise ValueError(f"disallowed expression: {type(node).__name__}")

    tree = _ast.parse(expr, mode="eval")
    return _ev(tree)


@tool
def compute(
    expression: Annotated[str, "Arithmetic to evaluate. Use the helpers "
                               "growth(curr,prior), cagr(end,start,years), "
                               "pct(part,whole); or plain +-*/() on numbers. "
                               "Examples: 'growth(3186,3045)', "
                               "'cagr(3186,2642,4)', 'pct(3.449953,3.776)', "
                               "'6.03+6.15+5.95+5.85+5.87'."],
) -> dict:
    """Deterministic calculator. **MANDATORY** for every derived number you
    state — YoY %, CAGR, share/ratio, percentage-point change, sum, average.
    Never compute these in your head: a wrong percentage in front of an
    executive is a critical failure. Pass the exact source values; this tool
    returns the precise result so you quote it verbatim.

    Returns the input expression, the full-precision result, and a value
    rounded to 2 dp. On any malformed/forbidden expression it returns an
    ``error`` instead of a result — fix the expression and retry."""
    try:
        val = _safe_eval(expression)
    except Exception as exc:  # noqa: BLE001
        return {"expression": expression, "error": str(exc), "result": None}
    if isinstance(val, list):
        return {"expression": expression, "result": val,
                "result_rounded": [round(float(x), 2) for x in val]}
    return {"expression": expression, "result": val,
            "result_rounded": round(float(val), 2)}


# Back-compat exports — the morning-brief orchestrator still imports the
# old names. Map them to the new tools so nothing breaks.
search_pq_archive       = search_parliamentary_replies
search_oil_india_data   = search_oil_data

ALL_TOOLS = [
    search_oil_data,
    search_parliamentary_replies,
    search_corporate_reports,
    compute,
    search_web,
    list_available_sources,
]
