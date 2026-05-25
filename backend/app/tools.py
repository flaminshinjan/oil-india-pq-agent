"""Tools exposed to the LangGraph agent.

We define three:
  - search_pq_archive     → semantic search over past parliamentary Q&A.
  - search_oil_india_data → semantic search over the DB/ corpus (production,
                            drilling, reserves, performance).
  - list_available_sources → quick directory of what the corpus actually
                            contains, so the agent can say "I don't have data
                            on X" with confidence instead of guessing.

Each returns a small JSON-serialisable dict that the agent can quote back in
its answer. Citations come back as `[file: <name>, section: <section>]`
fragments embedded in the result, so the LLM can attribute claims correctly.
"""
from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import tool

from .vectorstore import get_store


def _format_hit(hit) -> dict[str, Any]:
    md = hit.metadata or {}
    return {
        "source": md.get("source", ""),
        "filename": md.get("filename", ""),
        "session": md.get("session", ""),
        "kind": md.get("kind", ""),
        "section": md.get("section", ""),
        "score": round(float(hit.score), 3),
        "excerpt": hit.text,
        "sibling": bool(md.get("sibling_of")),
    }


@tool
def search_pq_archive(
    query: Annotated[str, "Natural-language search query describing the topic or PQ subject."],
    k: Annotated[int, "Number of past PQ excerpts to retrieve (1–10)."] = 5,
) -> dict:
    """Search the archive of past Oil India parliamentary questions and replies.

    Use this to find precedents — how OIL has phrased answers on topics like
    exploration, production, reserves, refining, CSR, recruitment, etc.
    Returns excerpts with file names so you can cite them.
    """
    k = max(1, min(int(k or 5), 10))
    hits = get_store().search("pq", query, k=k, with_siblings=True, max_total=12)
    return {
        "query": query,
        "count": len(hits),
        "results": [_format_hit(h) for h in hits],
    }


@tool
def search_oil_india_data(
    query: Annotated[str, "Natural-language search query for facts/figures (production, drilling, reserves, performance, discoveries)."],
    k: Annotated[int, "Number of factual excerpts to retrieve (1–10)."] = 5,
) -> dict:
    """Search OIL's structured-data corpus (production, drilling, workover,
    reserves & discoveries). Use this for any numeric or factual claim about
    Oil India Limited's operations.

    Returns markdown-rendered table excerpts with file/sheet citations.
    Sibling tables/sheets from the same source file are automatically
    included as additional context.
    """
    k = max(1, min(int(k or 5), 10))
    hits = get_store().search("db", query, k=k, with_siblings=True, max_total=12)
    return {
        "query": query,
        "count": len(hits),
        "results": [_format_hit(h) for h in hits],
    }


@tool
def list_available_sources() -> dict:
    """List every source document available to the agent, grouped by folder.

    Use this when the user asks something where you're unsure whether the
    corpus covers the topic — better to check the directory than to
    hallucinate.
    """
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
    return {
        "groups": out,
        "total_files": sum(len(v) for v in out.values()),
    }


ALL_TOOLS = [search_pq_archive, search_oil_india_data, list_available_sources]
