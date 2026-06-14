"""Tools exposed to the LangGraph agent.

The chat agent searches ALL internal sources for every substantive question —
there is no source hierarchy or prioritisation. It then reconciles the results
and flags any value that disagrees across sources:

    - `search_oil_data`              — DB/ Excel tables (production, drilling,
                                         workover, reserves, FY annexures).
                                         Synthetic JSON feeds (workforce,
                                         procurement, PPE) are EXCLUDED so the
                                         chat never cites a made-up table.
    - `search_parliamentary_replies` — Official Lok Sabha / Rajya Sabha PQ
                                         replies (most recent session first).
                                         Figures here are usable and citable.
    - `search_corporate_reports`     — Annual reports, BRSR, ESG Data Books
                                         (recency-ranked, latest FY first).
    - `search_web`                   — Tavily web search; external supplement,
                                         marked "from public web" in the answer.

Each search tool returns a small JSON-serialisable dict that the LLM can quote
back in its answer. Citations come back as `[file: <name>, section: <section>]`
or `[web: <title> — <url>]` so attribution is unambiguous.
"""
from __future__ import annotations

import os
import re
from typing import Annotated, Any

from langchain_core.tools import tool
from loguru import logger

from ..retrieval.vectorstore import get_store


# --- fiscal-year helpers for recency-aware ranking of corporate reports ---
_FY_QUERY_RE = re.compile(r"(20\d{2})\s*[-_/]\s*(\d{2})")


def _fy_end_year(report_fy: str) -> int:
    """'2024-25' -> 2025, '2020-21' -> 2021, '' -> 0."""
    m = re.match(r"(20\d{2})[-_](\d{2})", report_fy or "")
    return int(m.group(1)[:2] + m.group(2)) if m else 0


def _explicit_fys(query: str) -> set[str]:
    """Fiscal years the query NAMES explicitly, e.g. 'FY2022-23' -> {'2022-23'}.
    When the user pins a year we honour it; otherwise we tilt toward the latest."""
    return {f"{m.group(1)}-{m.group(2)}" for m in _FY_QUERY_RE.finditer(query or "")}


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
        "fy":       md.get("report_fy", ""),
        "buckets":  md.get("buckets", ""),
        "section":  md.get("section", ""),
        "score":    round(float(hit.score), 3),
        "excerpt":  hit.text,
        "sibling":  bool(md.get("sibling_of")),
    }


def _routed_search(collection: str, query: str, *, k: int, max_total: int):
    """Search `collection`, scoped to the query's topic bucket(s) when routing
    is confident, with a SOFT fallback: if the bucket-scoped search is empty or
    weak (top score < 0.45) we re-run unscoped. This keeps topical precision
    without ever hiding a source — bucketing scopes, it never blocks."""
    from ..retrieval.buckets import route_query

    store = get_store()
    cb = route_query(query)
    raw = store.search(collection, query, k=k, with_siblings=True, max_total=max_total, buckets=cb)
    if cb and (not raw or raw[0].score < 0.45):
        raw = store.search(collection, query, k=k, with_siblings=True, max_total=max_total, buckets=None)
    return raw


@tool
def search_oil_data(
    query: Annotated[str, "Natural-language search for numeric / FY-wise facts (production, drilling, reserves, performance)."],
    k:     Annotated[int, "Number of factual excerpts to retrieve (1–10)."] = 5,
) -> dict:
    """Searches OIL's structured DB tables: production, gas, reserves, RRR,
    wells, drilling, workover, and the FY 2025-26 performance annexures.

    Synthetic / placeholder JSON feeds are filtered out — every result
    you get back is from OIL's own ledger of operational disclosures.

    One of three PEER search tools — call it alongside
    `search_parliamentary_replies` and `search_corporate_reports` for any
    substantive question, then reconcile and flag any cross-source mismatch.
    """
    k = max(1, min(int(k or 5), 10))
    raw = _routed_search("db", query, k=k * 2, max_total=14)
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
    """Official Lok Sabha and Rajya Sabha question replies (Budget Session
    2026 → previous sessions). The richest, most on-point source for CSR,
    recruitment, welfare, partnerships, alternative-energy and policy /
    initiative questions — search it FIRST for those (alongside the others).
    Figures here ARE usable and citable (cite the reply's session/date); always
    cross-check them against the other sources and flag any mismatch.

    One of three PEER search tools — no source ladder. Ranked so the
    most-recent session bubbles up first.
    """
    k = max(1, min(int(k or 5), 10))
    raw = _routed_search("pq", query, k=k * 2, max_total=14)
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
    """Annual Reports, BRSR (Business Responsibility & Sustainability) reports
    and ESG Data Books (FY 2020-21 → FY 2024-25). Use for: financials, capex,
    sustainability metrics, LTIFR, governance, chairman-statement framing,
    diversity figures, training spend.

    One of three PEER search tools — call it alongside `search_oil_data` and
    `search_parliamentary_replies` for any substantive question, then reconcile
    and flag any cross-source mismatch.

    Results are recency-ranked: when the query does not pin a specific
    fiscal year, the **most recent** report (e.g. the FY2024-25 Annual
    Report) is surfaced first so "latest financials" never silently falls
    back to an older year. Naming a year in the query (e.g. "FY2022-23")
    pins results to that year instead.
    """
    k = max(1, min(int(k or 5), 10))
    # Fetch a wider candidate pool than we return, so the recency re-rank has
    # multiple fiscal years to choose from (raw embedding scores alone tend to
    # bury the latest Annual Report behind older ones for financial queries).
    # Bucket-scoped with a soft fallback (same policy as _routed_search).
    raw = _routed_search("pq", query, k=k * 4, max_total=k * 4 + 6)
    corp_hits = [h for h in raw if not (h.metadata or {}).get("source", "").startswith("PQs/")]

    asked = _explicit_fys(query)

    def _rank(h) -> float:
        md = h.metadata or {}
        score = float(h.score)
        fy = md.get("report_fy", "")
        if asked:
            # User pinned a year: float matching reports decisively, leave the
            # rest on raw relevance (still available as comparatives).
            return score + (0.35 if fy in asked else 0.0)
        # No year named -> tilt toward the most recent report. 0.05/yr reliably
        # floats the latest AR above near-tied older ones while still keeping
        # prior-year comparatives in the result set.
        return score + 0.05 * max(0, _fy_end_year(fy) - 2020)

    corp_hits.sort(key=_rank, reverse=True)
    corp_hits = corp_hits[:k]
    return {
        "query":   query,
        "count":   len(corp_hits),
        "note":    "Annual reports / BRSR / ESG only — recency-ranked (latest FY first unless a year is named).",
        "results": [_format_hit(h) for h in corp_hits],
    }


@tool
def search_web(
    query: Annotated[str, "Natural-language web search query."],
    k:     Annotated[int, "Number of web results to retrieve (1–5)."] = 4,
) -> dict:
    """Public web search via Tavily — an EXTERNAL supplement, outside OIL's
    own corpus. Use for context the internal sources don't hold (very recent
    industry news, third-party analysis, public-government releases not yet in
    the corpus).

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


def _facts_to_text(facts) -> str:
    """Normalise a section's `facts` (str | list[str] | list[dict]) to bullet text."""
    if not facts:
        return ""
    if isinstance(facts, str):
        return facts.strip()
    if isinstance(facts, (list, tuple)):
        lines = []
        for f in facts:
            if isinstance(f, dict):
                lines.append(" — ".join(str(v) for v in f.values() if v is not None))
            elif f is not None:
                lines.append(str(f))
        return "\n".join(f"- {ln}" for ln in lines if ln.strip())
    return str(facts)


_SECTION_EXPANDER_SYS = (
    "You write ONE section of a formal Oil India Limited (OIL) intelligence "
    "report for senior executives. Turn the supplied facts into 2–3 sentences "
    "of tight, factual analyst prose.\n"
    "ABSOLUTE RULES:\n"
    "- Use ONLY the facts given. Introduce NO number, date, percentage, name or "
    "claim that is not present in them. If the facts are thin, write less — never "
    "pad with invented detail.\n"
    "- Third person, formal, no marketing adjectives, no hedging. Surface any "
    "decline plainly; do not editorialise.\n"
    "- Output the prose ONLY — no heading, no bullet list, no preamble, no "
    "source line (the table and source note are added separately)."
)


async def _expand_section(llm, heading: str, facts_text: str) -> str:
    """Expand one section's facts into prose via the fast model. Falls back to
    the raw facts text on any error so the report never loses content."""
    from langchain_core.messages import HumanMessage, SystemMessage
    prompt = f"Report section heading: {heading or '(untitled)'}\n\nFacts:\n{facts_text}"
    try:
        resp = await llm.ainvoke([SystemMessage(content=_SECTION_EXPANDER_SYS),
                                  HumanMessage(content=prompt)])
        text = resp.content if isinstance(resp.content, str) else \
            "".join(b.get("text", "") for b in resp.content if isinstance(b, dict))
        return text.strip() or facts_text
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[generate_report] section expand failed ({heading!r}): {exc}")
        return facts_text


@tool
async def generate_report(
    title: Annotated[str, "Report title, e.g. 'OIL India — Production & Reserves Report (FY2025-26)'."],
    sections: Annotated[
        list,
        "Ordered list of section objects. Each section is a dict with: "
        "`heading` (str) and `facts` — the section's raw material as a list of "
        "terse data points / source-tagged figures (e.g. "
        "[\"Crude FY2024-25: 3.46 MMT (AR-25)\", \"FY2023-24: 3.13 MMT\", "
        "\"YoY +10.5% (compute)\"]). The server expands `facts` into polished "
        "prose IN PARALLEL — so pass facts, do NOT write full paragraphs "
        "yourself (that is what makes reports slow). Optional per section: "
        "`table` ({\"columns\": [str], \"rows\": [[cell,...]]}) for multi-year / "
        "multi-metric data, and `note` (str — the source citation). You MAY "
        "still pass a ready-written `body` instead of `facts` if you prefer; a "
        "section with a non-empty `body` is used verbatim and not re-expanded.",
    ],
    subtitle: Annotated[str, "Optional one-line subtitle / status line."] = "",
) -> dict:
    """Generate a polished, downloadable **PDF report**, Digby-branded (logo,
    headings, tables, footer). Call this whenever the user asks to "generate /
    create / make / download / export a report" (or a PDF / briefing note) on a
    topic.

    Build the report FIRST from the data tools (search_oil_data /
    search_corporate_reports) and `compute` — every figure must be real and
    sourced; never invent numbers, and put the source in each section's `note`.
    Pass each section's numbers as terse `facts`; the server fans the sections
    out to the fast model in parallel to write the prose, which is what keeps
    generation quick. Put any 3+-point or multi-year data in a `table`.

    Returns {report_url, filename, title}. After it returns, tell the user the
    report is ready and that a download button is shown — do NOT paste the raw
    URL or restate the whole report."""
    import asyncio

    try:
        from langchain_anthropic import ChatAnthropic
        from ..config import settings
        from ..core.report import build_report_pdf, REPORT_NAMES

        secs = [s for s in (sections or []) if isinstance(s, dict)]

        # Expand, in parallel, every section that supplied `facts` without a
        # ready body. Sections with a real `body` pass through untouched.
        expander = ChatAnthropic(
            model=settings.anthropic_fast_model,
            anthropic_api_key=settings.anthropic_api_key,
            temperature=0,
            max_tokens=400,
        )

        async def _resolve(sec: dict) -> dict:
            body = (sec.get("body") or "").strip()
            facts_text = _facts_to_text(sec.get("facts"))
            if not body and facts_text:
                body = await _expand_section(expander, sec.get("heading", ""), facts_text)
            out = {k: v for k, v in sec.items() if k != "facts"}
            out["body"] = body or facts_text
            return out

        resolved = await asyncio.gather(*[_resolve(s) for s in secs])

        spec = {"title": title, "subtitle": subtitle, "sections": list(resolved)}
        _path, filename, rid = build_report_pdf(spec)
        REPORT_NAMES[rid] = filename
        return {"report_url": f"/api/os/report/{rid}", "filename": filename,
                "title": title, "status": "ready"}
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[generate_report] failed: {exc}")
        return {"error": f"report generation failed: {exc}", "report_url": None}


# Back-compat exports — the morning-brief orchestrator still imports the
# old names. Map them to the new tools so nothing breaks.
search_pq_archive       = search_parliamentary_replies
search_oil_india_data   = search_oil_data

ALL_TOOLS = [
    search_oil_data,
    search_parliamentary_replies,
    search_corporate_reports,
    compute,
    generate_report,
    search_web,
    list_available_sources,
]
