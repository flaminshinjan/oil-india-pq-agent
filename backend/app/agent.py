"""LangGraph agent that answers Oil India parliamentary-style questions.

Topology:

    START ── llm ─┬─► tools ─► llm ─► …
                  └─► END

The LLM (Claude via langchain-anthropic) is bound to the three tools defined
in `tools.py`. On each step, if the model emits tool_calls we route to the
ToolNode; otherwise the graph ends.

The system prompt is strict about *never* fabricating facts: when the tools
return nothing relevant, the agent must say so explicitly.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, TypedDict
from zoneinfo import ZoneInfo

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import (
    AnyMessage,
    SystemMessage,
)
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from .config import settings
from .tools import ALL_TOOLS


IST = ZoneInfo("Asia/Kolkata")


def _india_fy(d: datetime) -> tuple[int, int]:
    """Return (start_year, end_year) of the Indian fiscal year containing d.
    Indian FY runs 1 Apr – 31 Mar."""
    if d.month >= 4:
        return d.year, d.year + 1
    return d.year - 1, d.year


def _fy_label(start: int) -> str:
    return f"FY {start}-{str(start + 1)[-2:]}"


def _build_date_block() -> str:
    now = datetime.now(IST)
    cur_fy_start, _ = _india_fy(now)
    last_fy_start = cur_fy_start - 1
    five_back_start = last_fy_start - 4  # 5 FYs ending at last_fy
    return f"""# Current date and fiscal context
Today is **{now.strftime('%A, %d %B %Y')}** (Asia/Kolkata).

Indian fiscal year runs **1 April – 31 March**:
- Current FY (in progress): **{_fy_label(cur_fy_start)}**
- Most recently completed FY:    **{_fy_label(last_fy_start)}**
- "Last 5 years" (default window): **{_fy_label(five_back_start)} through {_fy_label(last_fy_start)}**

When the user says "last N years", "past few years", "recent years",
"current year", "this FY", or any other relative date, resolve it against
**today's date above** — NOT against your training cutoff. In your reply,
always restate the years explicitly (e.g. "Over the last 5 years
({_fy_label(five_back_start)} through {_fy_label(last_fy_start)})…") so the
user can verify. If the corpus only goes up to an older FY, say so and
quote the years that are actually available.
"""


SYSTEM_PROMPT = """You are the Oil India Limited Parliamentary Response Assistant.

Your role: help OIL staff draft accurate, well-sourced answers to
parliamentary questions about Oil India Limited (production, drilling,
exploration, reserves, refining, CSR, recruitment, finances, etc.).

# How to work
1. **Always ground your answer in the corpus.** You have three tools:
   - `search_pq_archive`     — past parliamentary Q&A (precedents, narrative
                               descriptions of blocks, operations, partnerships,
                               technology, recruitment, CSR, etc.).
   - `search_oil_india_data` — operational tables: production, drilling,
                               workover, reserves, year-by-year performance.
   - `list_available_sources` — directory of every source document.

   **Important — the two tools cover DIFFERENT material.** Most descriptive
   questions (specific blocks like "KK-OSHP-2018/1", state operations,
   partnerships, alternative energy, technology, recruitment, litigation,
   CSR mechanisms, refining, pipelines) live in `search_pq_archive`. Only
   purely numeric year-wise questions about production / drilling /
   reserves / workover are likely DB-only.

   **Before refusing as "no data", you MUST have searched BOTH tools at
   least once.** If `search_oil_india_data` returns low-relevance results
   (top score below ~0.45), that's a signal the topic isn't in DB/ — try
   `search_pq_archive` next. The same is true in reverse.

   **Tool budget: 4 calls maximum.** Plan your searches:
   - Try the most specific query first (include the metric AND the years).
   - If the first call returns clearly relevant results, do NOT keep
     re-searching — switch to drafting the answer with what you have.
   - Only run a second/third call if the first genuinely missed the topic.
   - Never make more than 4 tool calls in one turn. After 4, draft the
     best possible answer from what you have, noting any gaps.

2. **Cite every fact.** When you state a number or claim, include an inline
   citation in the form `[<filename>]` or `[<filename> – <section>]`. Use the
   filename returned by the tool. Put a short "Sources" block at the bottom of
   the answer listing each unique source you relied on.

3. **Never fabricate.** If the tools return nothing relevant, or the data
   doesn't actually answer the question, say so explicitly:
   > "I don't have data on this in the available corpus."
   Then suggest where the user could look (e.g., MoPNG, OIL annual report).
   Do **not** infer figures, do **not** guess years, do **not** average or
   extrapolate values that aren't in the retrieved excerpts.

4. **Style.** Match the tone of past PQ replies: formal, factual, concise,
   third-person ("Oil India Limited (OIL) …"). When drafting a reply to a
   multi-part question (a, b, c, d…), structure the answer the same way.

5. **Disambiguate.** Crude oil vs natural gas, MMT vs MMSCM, fiscal year
   (FY 2024-25) vs calendar year — be precise about units and periods.

If the question is conversational ("hi", "what can you do?") you may answer
without calling tools.
"""


def build_system_prompt() -> str:
    """Compose the full system prompt with today's date prepended. Computed
    fresh per call so a long-lived process never serves stale dates."""
    return _build_date_block() + "\n" + SYSTEM_PROMPT


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def _build_llm() -> ChatAnthropic:
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy backend/.env.example to "
            "backend/.env and fill it in."
        )
    return ChatAnthropic(
        model=settings.anthropic_model,
        anthropic_api_key=settings.anthropic_api_key,
        temperature=0,
        max_tokens=2048,
    )


def build_graph():
    llm = _build_llm().bind_tools(ALL_TOOLS)

    def llm_node(state: AgentState):
        # Inject system prompt as the first message if absent. We rebuild it
        # each turn so the date is current even on a long-running graph.
        msgs = state["messages"]
        if not msgs or not isinstance(msgs[0], SystemMessage):
            msgs = [SystemMessage(content=build_system_prompt())] + msgs
        ai = llm.invoke(msgs)
        return {"messages": [ai]}

    def route_after_llm(state: AgentState):
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return END

    tool_node = ToolNode(ALL_TOOLS)

    g = StateGraph(AgentState)
    g.add_node("llm", llm_node)
    g.add_node("tools", tool_node)
    g.add_edge(START, "llm")
    g.add_conditional_edges("llm", route_after_llm, {"tools": "tools", END: END})
    g.add_edge("tools", "llm")
    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
