"""Shared LangGraph factory used by every domain agent.

A domain agent is just (system_prompt, [tools]). Same wiring as the original
single-purpose chat — we just parameterise it so each agent has its own
brain (prompt) and its own toolbox.
"""
from __future__ import annotations

from typing import Annotated, Callable, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AnyMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from ..config import settings


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def _llm(model: str | None = None) -> ChatAnthropic:
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy backend/.env.example to "
            "backend/.env and fill it in."
        )
    return ChatAnthropic(
        model=model or settings.anthropic_model,
        anthropic_api_key=settings.anthropic_api_key,
        temperature=0,
        max_tokens=16384,
    )


def build_graph(system_prompt_fn: Callable[[], str], tools: list, *, model: str | None = None):
    """Compile a LangGraph for an agent with a given prompt builder + tools.

    `system_prompt_fn` is re-evaluated each turn so the date block stays
    current — important for relative-date reasoning. `model` overrides the
    default chat model (used for the faster report-generation graph).
    """
    llm = _llm(model).bind_tools(tools)

    def llm_node(state: AgentState):
        msgs = state["messages"]
        if not msgs or not isinstance(msgs[0], SystemMessage):
            msgs = [SystemMessage(content=system_prompt_fn())] + msgs
        ai = llm.invoke(msgs)
        return {"messages": [ai]}

    def route(state: AgentState):
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return END

    g = StateGraph(AgentState)
    g.add_node("llm", llm_node)
    g.add_node("tools", ToolNode(tools))
    g.add_edge(START, "llm")
    g.add_conditional_edges("llm", route, {"tools": "tools", END: END})
    g.add_edge("tools", "llm")
    return g.compile()
