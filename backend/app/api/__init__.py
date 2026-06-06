"""FastAPI routers, one module per surface:

  - chat   /api/chat            streaming NDJSON conversation
  - os     /api/os/*            morning brief + signals + agent ops
  - health /api/health, /api/sources

main.py imports and `include_router`s each. Keep this directory shallow —
no domain logic should live here, only routing + serialisation.
"""
