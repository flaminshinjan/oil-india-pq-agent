# Oil India Parliamentary-Response Agent

An AI assistant that drafts answers to parliamentary questions about Oil India
Limited by retrieving from past PQs and OIL's own production / drilling /
reserves data. Built with **LangGraph + Anthropic Claude** on the backend and
**Next.js** on the frontend.

## What it does

The agent has three tools and is instructed to never fabricate:

| Tool | Source | Purpose |
| --- | --- | --- |
| `search_pq_archive` | `Parliamentary Replies/PQs/**` | Past Q&A — used for precedent & phrasing. |
| `search_oil_india_data` | `Parliamentary Replies/DB/**` | Production, drilling, reserves figures. |
| `list_available_sources` | the whole corpus | Lets the agent confirm whether the corpus actually covers a topic before answering. |

If the corpus doesn't contain the answer, the agent says so explicitly
("I don't have data on this in the available corpus.") instead of guessing.

## Layout

```
oil_india_demo/
├── Parliamentary Replies/      ← source documents (PQs + DB + IGNORE)
├── backend/
│   ├── app/
│   │   ├── extractors.py       ← docx / xlsx / pdf → markdown chunks
│   │   ├── ingest.py           ← CLI: walk corpus → embed → Chroma
│   │   ├── vectorstore.py      ← Chroma + sentence-transformers
│   │   ├── tools.py            ← the 3 LangGraph tools
│   │   ├── agent.py            ← LangGraph state graph (llm ↔ tools)
│   │   ├── main.py             ← FastAPI + streaming chat endpoint
│   │   └── schemas.py          ← wire-protocol types
│   ├── .env                    ← API key + paths (gitignored)
│   ├── chroma_db/              ← persistent vector store (created on ingest)
│   └── requirements.txt
└── frontend/
    ├── app/                    ← Next.js app-router pages
    ├── components/
    │   ├── Chat.tsx            ← state + streaming wire-event handling
    │   ├── Message.tsx         ← assistant text & user bubble
    │   └── ToolCard.tsx        ← collapsible tool-call card
    ├── lib/
    │   ├── api.ts              ← NDJSON stream reader
    │   └── types.ts            ← shared TS types
    └── package.json
```

## Setup

### 1. Backend

```bash
cd backend

# create venv + install
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# configure
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY=sk-ant-...

# ingest the corpus (first run; ~30s)
.venv/bin/python -m app.ingest --reset

# start the API
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

`/api/health` should now report a non-zero `vector_store.pq` count and
`anthropic_key_set: true`.

### 2. Frontend

```bash
cd frontend
npm install
BACKEND_PORT=8765 npm run dev
```

Open <http://localhost:3737>.

## How the streaming protocol works

The backend's `/api/chat` endpoint streams **newline-delimited JSON**, one
event per line. The frontend renders each `type` as a distinct UI block:

```jsonc
{"type":"text", "delta":"Based on the search results, "}
{"type":"tool_call", "id":"...", "name":"search_oil_india_data", "args":{"query":"crude oil production FY 2024-25"}}
{"type":"tool_result", "id":"...", "name":"search_oil_india_data", "result":{"results":[{...}]}}
{"type":"text", "delta":"OIL produced 3.46 MMT…"}
{"type":"done", "citations":[{"filename":"…","section":"…"}]}
```

This gives the user four visually distinct message types — user bubble,
assistant text, tool call (collapsible card), and a citations footer.

## Common operations

```bash
# Re-ingest after dropping new files into Parliamentary Replies/
.venv/bin/python -m app.ingest --reset

# Test a tool directly (without LLM cost)
.venv/bin/python -c "from app.tools import search_oil_india_data as t; \
  print(t.invoke({'query':'drilling 2024-25','k':3}))"

# Inspect what the agent will see for a query
curl -sN -X POST http://127.0.0.1:8765/api/chat \
     -H 'Content-Type: application/json' \
     -d '{"messages":[{"role":"user","content":"How many wells did OIL drill last year?"}]}'
```

## Design notes

- **Embeddings are local** (`sentence-transformers/all-MiniLM-L6-v2`). The
  Anthropic API is only used for reasoning, so the vector store can be
  rebuilt offline for free.
- **One chunk per table / sheet**, plus narrative paragraphs. Long chunks are
  split by `RecursiveCharacterTextSplitter` with overlap; short ones are
  kept whole so the LLM sees full table context.
- **Every chunk's text starts with a breadcrumb** (`File: … | Session: … | Kind: …`)
  so retrieval results stay self-explanatory even out of context.
- **Two collections** (PQs vs DB) so the agent can target precedent vs. facts.
- **Citations are extracted from tool results**, not parsed out of the LLM's
  answer — the frontend's "Sources" chips are guaranteed to reflect what was
  actually retrieved.
