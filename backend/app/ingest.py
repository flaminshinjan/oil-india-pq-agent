"""Ingest the Parliamentary Replies corpus into Chroma.

- Files under `PQs/` go into the `oil_india_pqs` collection (the agent uses
  these as style/precedent references for how OIL has answered before).
- Files under `DB/` go into the `oil_india_db` collection (production,
  drilling, reserves — the factual ground truth).
- The `IGNORE/` directory is, as named, skipped.

Run:  python -m app.ingest
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from tqdm import tqdm

from .config import settings
from .extractors import extract, iter_documents, Chunk
from .vectorstore import get_store


SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=1400,
    chunk_overlap=180,
    separators=["\n\n", "\n", ". ", " ", ""],
)

# DB/ chunks are small structured tables. Splitting them separates the
# natural-language descriptor (good for retrieval matching) from the numeric
# body (the actual values the agent needs to quote). Keep them whole.
DB_KEEP_WHOLE_UNTIL = 8000


def _session_from_path(rel: Path) -> str:
    """Top-level PQ folder ("Budget Session 2025", "Monsoon 2025", ...)."""
    parts = rel.parts
    if len(parts) >= 2 and parts[0] == "PQs":
        return parts[1]
    return ""


def _doc_kind(rel: Path) -> str:
    """Question vs Reply vs status vs other — derived from folder name."""
    parts_lower = [p.lower() for p in rel.parts]
    if any("pq reply" in p for p in parts_lower):
        return "reply"
    if any("pq question" in p for p in parts_lower):
        return "question"
    if any("status" in p for p in parts_lower):
        return "status"
    return "other"


def _split_chunks(chunks: list[Chunk], header_prefix: str, *, keep_whole: bool = False) -> tuple[list[str], list[dict]]:
    """Split each Chunk's text into sub-chunks for embedding, copying metadata
    and prepending a stable breadcrumb so retrieval results stay
    self-explanatory.

    `keep_whole=True` skips splitting up to DB_KEEP_WHOLE_UNTIL chars — used
    for structured-data sheets/tables where splitting would orphan numeric
    values from the descriptor.
    """
    texts: list[str] = []
    metas: list[dict] = []
    for ch in chunks:
        limit = DB_KEEP_WHOLE_UNTIL if keep_whole else 1400
        pieces = SPLITTER.split_text(ch.text) if len(ch.text) > limit else [ch.text]
        for idx, piece in enumerate(pieces):
            body = f"{header_prefix}\n\n{piece}".strip()
            md = dict(ch.metadata)
            md["chunk_index"] = idx
            md["chunk_total"] = len(pieces)
            texts.append(body)
            metas.append(md)
    return texts, metas


def _build_header(rel: Path, kind: str, session: str) -> str:
    bits = [f"File: {rel.as_posix()}"]
    if session:
        bits.append(f"Session: {session}")
    if kind and kind != "other":
        bits.append(f"Kind: {kind}")
    return " | ".join(bits)


def ingest(root: Path, *, reset: bool = False) -> None:
    store = get_store()

    if reset:
        print("[ingest] Resetting collections…")
        try:
            store.client.delete_collection(settings.pq_collection)
            store.client.delete_collection(settings.db_collection)
        except Exception:
            pass
        # Recreate
        from .vectorstore import VectorStore
        global _store  # noqa
        store = VectorStore()

    files = list(iter_documents(root))
    # Drop IGNORE/ subtree
    files = [f for f in files if "IGNORE" not in f.relative_to(root).parts]

    print(f"[ingest] {len(files)} files under {root}")
    pq_texts: list[str] = []
    pq_metas: list[dict] = []
    db_texts: list[str] = []
    db_metas: list[dict] = []

    for path in tqdm(files, desc="extract"):
        rel = path.relative_to(root)
        kind = _doc_kind(rel)
        session = _session_from_path(rel)
        header = _build_header(rel, kind, session)

        chunks = extract(path)
        if not chunks:
            continue

        is_db = rel.parts[0] == "DB"
        texts, metas = _split_chunks(chunks, header, keep_whole=is_db)
        common = {
            "source": rel.as_posix(),
            "filename": path.name,
            "session": session,
            "kind": kind,
        }
        for m in metas:
            m.update(common)

        if is_db:
            db_texts.extend(texts)
            db_metas.extend(metas)
        else:
            pq_texts.extend(texts)
            pq_metas.extend(metas)

    print(f"[ingest] embedding+writing  PQ chunks={len(pq_texts)}  DB chunks={len(db_texts)}")
    t0 = time.time()
    # Batch to keep memory reasonable
    _batched_add(store, "pq", pq_texts, pq_metas)
    _batched_add(store, "db", db_texts, db_metas)
    print(f"[ingest] done in {time.time() - t0:.1f}s. counts={store.stats()}")


def _batched_add(store, name: str, texts: list[str], metas: list[dict], batch: int = 128) -> None:
    for i in tqdm(range(0, len(texts), batch), desc=f"embed:{name}"):
        store.add(name, texts[i:i + batch], metas[i:i + batch])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=settings.data_root)
    ap.add_argument("--reset", action="store_true", help="wipe collections first")
    args = ap.parse_args()
    ingest(args.root, reset=args.reset)


if __name__ == "__main__":
    main()
