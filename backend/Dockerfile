# Backend — FastAPI + LangGraph agent for Oil India PQ Assistant.
# The image bakes in the pre-built Chroma vector store and the
# sentence-transformer model, so the container is ready to serve as
# soon as it boots — no first-request download, no re-ingestion.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/hf-cache \
    SENTENCE_TRANSFORMERS_HOME=/opt/hf-cache

WORKDIR /app

# System deps: only what python-docx / pdfplumber / chromadb need at runtime.
# torch wheel for arm64 is large; keep apt list minimal.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Pre-download the embedding model so the first request doesn't have to.
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Ship the pre-ingested Chroma DB.
COPY chroma_db /app/chroma_db

# Ship the structured-data Excel/Word source files for the deterministic
# morning-brief scans (production agent reads RRR, drilling agent reads
# target-vs-actual). These are 4 small files (~100KB total).
COPY data /app/data

# Source PDFs (annual reports, BRSR, ESG) the citations link back to.
# ~75 MB; lets /api/sources/<filename> serve them for inline preview.
COPY sources /app/sources

# App code.
COPY app /app/app

ENV CHROMA_DIR=/app/chroma_db \
    DATA_ROOT=/app/data \
    EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2 \
    ANTHROPIC_MODEL=claude-haiku-4-5-20251001 \
    PORT=8080

EXPOSE 8080

# Single worker — the agent is mostly I/O-bound (Anthropic + Chroma), and
# multi-worker would duplicate the loaded embedding model in memory.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --no-access-log"]
