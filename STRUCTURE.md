# Repo structure

Two apps, deployed independently on Fly. Both are self-contained and follow
language-idiomatic packaging.

```
oil_india_demo/
├── backend/                       Python · FastAPI · LangGraph · Anthropic · Chroma
│   ├── app/
│   │   ├── main.py                FastAPI factory + startup hooks. No domain logic.
│   │   ├── config.py              Pydantic-style Settings loaded from .env
│   │   │
│   │   ├── api/                   ── HTTP surface (FastAPI routers)
│   │   │   ├── chat.py            POST /api/chat               (NDJSON streaming chat)
│   │   │   ├── os.py              GET/POST /api/os/*           (brief, signals, refresh, agents)
│   │   │   └── health.py          GET /api/health, /api/sources
│   │   │
│   │   ├── agents/                ── Domain agents (one engine, many brains)
│   │   │   ├── base.py            LangGraph factory: (system_prompt_fn, tools) → graph
│   │   │   ├── tools.py           Three LangGraph tools (PQ search, data search, list sources)
│   │   │   ├── production.py      scan() reads 10-Year Production Excel → RRR/reserves signals
│   │   │   ├── drilling.py        scan() reads FY-perf Excel → target-vs-actual signals
│   │   │   ├── hse.py             scan() emits PPE/safety signals (synthetic until CV lands)
│   │   │   ├── procurement.py     scan() emits the curated RFP/bid-scoring signal
│   │   │   ├── workforce.py       scan() emits attrition/headcount signals (synthetic)
│   │   │   └── pq.py              PQ-drafting agent — graph used by /api/chat
│   │   │
│   │   ├── orchestrator/          ── Cross-agent intelligence layer
│   │   │   └── brief.py           Runs every agent's scan() in parallel, ranks signals,
│   │   │                          fuses Production + Drilling into the headline insight.
│   │   │
│   │   ├── core/                  ── Shared, domain-agnostic infra
│   │   │   ├── data.py            pandas/openpyxl readers for the canonical Excel/Word
│   │   │   ├── cache.py           Disk-backed LLM response cache (rehearsed overrides supported)
│   │   │   ├── signals.py         SQLite signals/events store — the agent shared-context bus
│   │   │   └── prompts.py         Date / Indian-FY block prepended to every agent prompt
│   │   │
│   │   ├── retrieval/             ── RAG layer
│   │   │   ├── vectorstore.py     Chroma wrapper + sentence-transformer embeddings
│   │   │   ├── extractors.py      docx / xlsx / pdf → markdown chunks
│   │   │   └── ingest.py          CLI: python -m app.retrieval.ingest
│   │   │
│   │   └── schemas/               ── HTTP wire types (Pydantic)
│   │       └── wire.py            Streaming event types: WireText, WireToolCall, ...
│   │
│   ├── data/DB/                   Bundled canonical Excel/Word for the deterministic scans
│   ├── chroma_db/                 Pre-ingested vector store (gitignored; rebuild via ingest)
│   ├── Dockerfile + fly.toml      Deploys to oil-india-pq-backend.fly.dev
│   ├── requirements.txt + .env.example
│   └── README.md
│
├── frontend/                      Next.js 14 · App Router · TypeScript · streaming NDJSON
│   ├── app/
│   │   ├── layout.tsx             Root layout
│   │   ├── globals.css            Theme tokens (light landing + dark Atlas command-centre)
│   │   ├── page.tsx               / → Atlas command centre (Morning Brief, Agents, Copilot, PQ tabs)
│   │   └── chat/page.tsx          /chat → original PQ chat surface (kept as a deep tool)
│   │
│   ├── components/
│   │   ├── atlas/                 Atlas-specific surfaces
│   │   │   └── AtlasChat.tsx      Free-text Q&A in copilot or PQ mode (inside Atlas tabs)
│   │   └── chat/                  Reusable chat primitives
│   │       ├── Chat.tsx           Conversation-aware streaming chat
│   │       ├── Composer.tsx       Auto-grow textarea + send/stop button
│   │       ├── Message.tsx        User bubble + assistant body + citations
│   │       ├── ToolCard.tsx       Compact tool-call chips + collapsible detail panel
│   │       └── Sidebar.tsx        Conversation history (groupByDate, rename, delete)
│   │
│   ├── lib/
│   │   ├── api.ts                 streamChat() — NDJSON reader for /api/chat
│   │   ├── os.ts                  Atlas OS API helpers + types (Brief, Signal, Severity)
│   │   ├── storage.ts             localStorage-backed conversation store + grouping
│   │   └── types.ts               Shared TS types (Message, WireEvent, AssistantBlock)
│   │
│   ├── Dockerfile + fly.toml      Deploys to oil-india-pq-frontend.fly.dev
│   ├── next.config.js             Standalone build; rewrites /api/* → BACKEND_URL
│   └── package.json
│
├── Parliamentary Replies/         Source corpus (PQs/, DB/) — checked in for reproducibility
│   ├── PQs/                       Past parliamentary Q&A sessions (.docx kept; PDFs gitignored)
│   ├── DB/                        Canonical Excel/Word (also bundled into backend/data/DB)
│   └── IGNORE/                    Earlier draft material, skipped at ingestion
│
└── README.md                      Quickstart + architecture notes
```

## Why this shape

- **`api/` does only routing + serialisation.** All real work lives in domain
  packages so handlers stay short and testable.
- **`agents/` is closed under "one brain = one file".** Each domain agent is a
  prompt + a `scan()` + (sometimes) a graph. Adding an agent is one new module
  plus one line in `agents/__init__.py:DOMAIN_AGENTS`.
- **`core/` is domain-free.** Anything every other package can depend on — no
  reverse imports allowed.
- **`retrieval/` owns vector + ingestion.** When the corpus changes, only this
  package changes.
- **`orchestrator/` is the only place that knows about *every* agent.** Single
  spot for cross-domain fusion logic (the headline insight).

## Conventions

- Relative imports always go through packages: `from ..core import signals`.
- Each package has an `__init__.py` with a one-paragraph docstring describing
  its responsibility.
- Domain agents own their system prompt; shared bits (date block) come from
  `core/prompts.py`.
- The signals store uses `(agent, title)` as the dedup key, so re-runs of a
  scan upsert rather than duplicate.
- Frontend components are grouped by feature, not by type — `atlas/` for OS
  surfaces, `chat/` for reusable chat primitives.
