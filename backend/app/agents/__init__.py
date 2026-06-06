"""Domain agents for Atlas.

Same engine (LangGraph factory in `base.py`, shared tools in `tools.py`),
different brains. Each module exposes:

  - SYSTEM_PROMPT_TAIL  : the agent's scope blurb (for /api/os/agents)
  - scan() -> [Signal]  : run the agent in 'background mode' — read its
                          data, publish observations to the shared store

The orchestrator imports `scan` from each module and runs them in parallel
to refresh the morning brief.
"""
from . import production, drilling, hse, procurement, workforce, pq


DOMAIN_AGENTS = {
    "production":  production,
    "drilling":    drilling,
    "hse":         hse,
    "procurement": procurement,
    "workforce":   workforce,
    "pq":          pq,
}

ALL_AGENTS = list(DOMAIN_AGENTS.keys())

__all__ = ["DOMAIN_AGENTS", "ALL_AGENTS"]
