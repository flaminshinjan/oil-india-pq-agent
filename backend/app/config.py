"""Runtime configuration loaded from environment / .env file."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend/ directory
_BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_DIR / ".env")


class Settings:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
    # Faster model used only for PDF/report generation, which is layout of
    # already-retrieved facts and streams a large payload — Haiku is ~2-3x
    # faster there. Chat/drafting stays on `anthropic_model` for guardrails.
    anthropic_fast_model: str = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5-20251001")

    # `data_root` is the SOURCE CORPUS — walked by the ingest CLI to feed
    # Chroma. Locally this is the full Parliamentary Replies tree. In prod
    # it's overridden to point at the bundled runtime data.
    data_root: Path = Path(os.getenv(
        "DATA_ROOT",
        "/Users/shinjan/Desktop/oil_india_demo/Parliamentary Replies",
    ))

    # `runtime_data_dir` is what the AGENTS read at runtime — DB/ Excel
    # files for deterministic scans, synthetic/ JSON for the HSE / Procurement
    # / Workforce agents. Defaults to backend/data/ which is the bundle the
    # Docker image ships, so prod always finds it. Locally it also defaults
    # to backend/data/ (the same files, kept in-repo for the build context).
    runtime_data_dir: Path = Path(os.getenv(
        "RUNTIME_DATA_DIR",
        str(_BACKEND_DIR / "data"),
    ))

    chroma_dir: Path = Path(os.getenv(
        "CHROMA_DIR",
        str(_BACKEND_DIR / "chroma_db"),
    ))
    embed_model: str = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    cors_origins: list[str] = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://localhost:3737,https://oil-india-pq-frontend.fly.dev",
        ).split(",")
        if o.strip()
    ]

    pq_collection: str = "oil_india_pqs"
    db_collection: str = "oil_india_db"


settings = Settings()
