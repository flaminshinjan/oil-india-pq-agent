"""Shared RAG scan helper used by every domain agent.

`llm_scan()` is the only function an agent needs to call to produce signals:

  1. Run vector search over Chroma using the agent's domain queries.
  2. Compose a structured prompt (date block + agent role + retrieved
     chunks).
  3. Ask Claude to emit a JSON array of signal objects.
  4. Parse, validate, publish to the signals store.

The LLM is the intelligence — no Python-side analysis logic, no hardcoded
strings. Replace the JSON file or the corpus and the next scan re-derives
everything from scratch.
"""
from __future__ import annotations

import json
import re
from typing import Iterable

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from ..config import settings
from ..core import cache, signals
from ..core.prompts import date_block
from ..retrieval.vectorstore import get_store


SCAN_PROMPT_HEAD = """You are a domain agent inside Atlas, an advisory
intelligence OS for Oil India Limited. Atlas is **read-only** — you observe,
reason, and surface what matters. You never propose actions, only signals.

Your job on each scan: read the retrieved excerpts below and decide which
1–3 observations are most worth surfacing to a CXO right now. Be specific:
quote numbers exactly from the data, name files/sections you used.

# Output contract — STRICT
Return a **JSON array** of 1–3 signal objects. Nothing else — no prose, no
code fences. Each signal:

{
  "severity": "info" | "low" | "med" | "high" | "critical",
  "title":    string (<= 90 chars, no markdown, no quotes around it),
  "body":     string (2–5 sentences, may use **bold** for key numbers,
                      always quote exact figures from the excerpts),
  "refs":     [ { "filename": "<source filename>", "section": "<section>" } ]
              — only files actually used in `body`, 1–3 entries,
  "metric":   optional object with the numeric primitives behind the signal
              (kind + raw values), free-form
}

Severity guidance:
- critical: imminent safety/financial risk, action needed today
- high:     persistent gap from target / clear adverse trend
- med:      noteworthy but not urgent (e.g., off-baseline)
- low/info: contextual, FYI

Quality rules:
- Quote numbers EXACTLY as in the excerpts (don't round, don't paraphrase).
- Cite filenames EXACTLY as they appear in the excerpts.
- If nothing in the excerpts is worth surfacing, return [] (an empty array).
- Never invent data not present in the excerpts.
"""


def _format_hit(h, idx: int) -> str:
    """Render one retrieval hit as a labelled block for the prompt."""
    md = h.metadata or {}
    src = md.get("filename") or md.get("source") or "?"
    section = md.get("section") or ""
    score = round(float(getattr(h, "score", 0)), 2)
    return (
        f"--- excerpt #{idx} (score {score}) ---\n"
        f"filename: {src}\n"
        f"section:  {section}\n"
        f"---\n"
        f"{h.text}\n"
    )


def _retrieve(queries: Iterable[str], k_per_query: int = 4) -> list:
    """Run each query over both Chroma collections, merge, dedupe by source+section."""
    store = get_store()
    seen: set[tuple[str, str]] = set()
    out = []
    for q in queries:
        for coll in ("db", "pq"):
            try:
                for h in store.search(coll, q, k=k_per_query, with_siblings=True):
                    key = (h.metadata.get("source", ""), h.metadata.get("section", ""))
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(h)
            except Exception as e:
                print(f"[rag] search failed coll={coll} q={q!r}: {e}")
    return out


def _parse_signals_json(text: str) -> list[dict]:
    """Extract a JSON array of signals from the model output, tolerant to
    surrounding prose or code fences."""
    text = text.strip()
    # Try direct parse.
    try:
        v = json.loads(text)
        if isinstance(v, list):
            return v
    except json.JSONDecodeError:
        pass
    # Try fenced code block.
    m = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if m:
        try:
            v = json.loads(m.group(1))
            if isinstance(v, list):
                return v
        except json.JSONDecodeError:
            pass
    # Try slicing between first '[' and last ']'.
    start, end = text.find("["), text.rfind("]")
    if start >= 0 and end > start:
        try:
            v = json.loads(text[start : end + 1])
            if isinstance(v, list):
                return v
        except json.JSONDecodeError:
            pass
    return []


def _to_signals(agent: str, raw: list[dict]) -> list[signals.Signal]:
    out: list[signals.Signal] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        body = (item.get("body") or "").strip()
        if not title or not body:
            continue
        sev = (item.get("severity") or "info").lower()
        if sev not in {"info", "low", "med", "high", "critical"}:
            sev = "info"
        refs = item.get("refs") or []
        if not isinstance(refs, list):
            refs = []
        out.append(signals.Signal(
            agent=agent,
            severity=sev,
            title=title[:120],
            body=body,
            refs=[r for r in refs if isinstance(r, dict)],
            metric=item.get("metric") if isinstance(item.get("metric"), dict) else None,
        ))
    return out


def _llm():
    return ChatAnthropic(
        model=settings.anthropic_model,
        anthropic_api_key=settings.anthropic_api_key,
        temperature=0,
        max_tokens=2048,
    )


def llm_scan(
    *,
    agent: str,
    role: str,
    queries: list[str],
    extra_context: str = "",
    k_per_query: int = 4,
) -> list[signals.Signal]:
    """Run one RAG scan for a domain agent. Cached by (model, prompt) so
    repeat scans against unchanged data are instant.
    """
    hits = _retrieve(queries, k_per_query=k_per_query)
    if not hits and not extra_context:
        return []

    retrieved_block = "\n".join(_format_hit(h, i + 1) for i, h in enumerate(hits[:14]))

    system = (
        SCAN_PROMPT_HEAD
        + "\n\n"
        + date_block()
        + "\n# Agent role\n"
        + role.strip()
    )
    user_parts = []
    if extra_context.strip():
        user_parts.append("# Live state (read fresh this scan)\n" + extra_context.strip())
    user_parts.append("# Retrieved excerpts (top results across DB + PQ)\n" + retrieved_block)
    user_parts.append("Now emit the JSON signal array.")
    user = "\n\n".join(user_parts)

    cache_key_prompt = f"{system}\n----\n{user}"
    cached = cache.get(settings.anthropic_model, cache_key_prompt, scope=f"scan/{agent}")
    if cached and cached.text:
        raw = _parse_signals_json(cached.text)
        sigs = _to_signals(agent, raw)
        signals.publish_many(sigs)
        return sigs

    try:
        resp = _llm().invoke([SystemMessage(content=system), HumanMessage(content=user)])
        text = resp.content if isinstance(resp.content, str) else "".join(
            (b.get("text", "") if isinstance(b, dict) else str(b)) for b in resp.content
        )
    except Exception as e:
        print(f"[llm_scan] {agent} LLM call failed: {e}")
        return []

    cache.put(
        settings.anthropic_model,
        cache_key_prompt,
        cache.CachedResponse(text=text),
        scope=f"scan/{agent}",
    )

    raw = _parse_signals_json(text)
    sigs = _to_signals(agent, raw)
    signals.publish_many(sigs)
    return sigs
