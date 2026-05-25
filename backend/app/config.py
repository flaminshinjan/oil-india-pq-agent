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
    data_root: Path = Path(os.getenv(
        "DATA_ROOT",
        "/Users/shinjan/Desktop/oil_india_demo/Parliamentary Replies",
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
