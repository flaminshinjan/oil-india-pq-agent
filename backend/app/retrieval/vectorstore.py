"""Chroma-backed vector store with two collections (PQ archive + DB facts).

Embeddings are produced by a local sentence-transformer so no external
embedding API is needed. Anthropic Claude handles the reasoning over the
retrieved chunks.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from ..config import settings


@dataclass
class SearchHit:
    text: str
    metadata: dict
    score: float  # 0..1, higher is better


class VectorStore:
    _embedder: Optional[SentenceTransformer] = None

    def __init__(self, persist_dir: Path | None = None):
        self.persist_dir = persist_dir or settings.chroma_dir
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.pq = self.client.get_or_create_collection(
            settings.pq_collection,
            metadata={"hnsw:space": "cosine"},
        )
        self.db = self.client.get_or_create_collection(
            settings.db_collection,
            metadata={"hnsw:space": "cosine"},
        )

    # ---- embedder (lazy, shared) ----
    @classmethod
    def embedder(cls) -> SentenceTransformer:
        if cls._embedder is None:
            cls._embedder = SentenceTransformer(settings.embed_model)
        return cls._embedder

    def embed(self, texts: list[str]) -> list[list[float]]:
        emb = self.embedder().encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
        return emb.tolist()

    # ---- write ----
    def add(self, collection_name: str, texts: list[str], metadatas: list[dict]) -> int:
        if not texts:
            return 0
        coll = self.pq if collection_name == "pq" else self.db
        # Build ids with full-text hash, then dedupe within the batch — different
        # files can share boilerplate (letterhead, signatory) and produce the
        # same chunk; we only want to embed/store it once.
        ids_all = [self._make_id(m, t) for m, t in zip(metadatas, texts)]
        seen: set[str] = set()
        dedup_texts: list[str] = []
        dedup_metas: list[dict] = []
        dedup_ids: list[str] = []
        for i, _id in enumerate(ids_all):
            if _id in seen:
                continue
            seen.add(_id)
            dedup_ids.append(_id)
            dedup_texts.append(texts[i])
            dedup_metas.append(metadatas[i])
        if not dedup_texts:
            return 0
        embeddings = self.embed(dedup_texts)
        coll.upsert(
            ids=dedup_ids,
            documents=dedup_texts,
            metadatas=dedup_metas,
            embeddings=embeddings,
        )
        return len(dedup_texts)

    @staticmethod
    def _make_id(meta: dict, text: str) -> str:
        body = hashlib.sha1(text.encode("utf-8")).hexdigest()
        key = f"{meta.get('source', '')}::{meta.get('section', '')}::{meta.get('chunk_index', 0)}::{body}"
        return hashlib.sha1(key.encode("utf-8")).hexdigest()

    # ---- read ----
    def search(
        self,
        collection_name: str,
        query: str,
        k: int = 5,
        *,
        with_siblings: bool = False,
        max_total: int = 12,
    ) -> list[SearchHit]:
        """Embedding search. When `with_siblings=True`, also pull other table_*
        and sheet:* chunks from the same source as any top hit — this catches
        the common case where retrieval surfaces a Q/A table (`table_1`) but
        the actual numeric data lives in a sibling annexure (`table_2`,
        `table_3`).
        """
        coll = self.pq if collection_name == "pq" else self.db
        if coll.count() == 0:
            return []
        emb = self.embed([query])[0]
        res = coll.query(query_embeddings=[emb], n_results=k)
        hits: list[SearchHit] = []
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        for d, m, dist in zip(docs, metas, dists):
            score = max(0.0, 1.0 - float(dist))
            hits.append(SearchHit(text=d, metadata=m or {}, score=score))

        if not with_siblings or not hits:
            return hits

        return self._expand_with_siblings(coll, hits, max_total=max_total)

    @staticmethod
    def _is_data_section(section: str) -> bool:
        return section.startswith("table_") or section.startswith("sheet:")

    def _expand_with_siblings(
        self,
        coll,
        primary: list[SearchHit],
        *,
        max_total: int,
        max_per_source: int = 3,
    ) -> list[SearchHit]:
        seen: set[tuple[str, str]] = {
            (h.metadata.get("source", ""), h.metadata.get("section", "")) for h in primary
        }

        # Sources where the hit is a data table — siblings of these are worth pulling.
        # Map source → best parent score, so siblings can inherit a discounted score.
        sources_to_expand: dict[str, float] = {}
        for h in primary:
            sec = h.metadata.get("source", ""), h.metadata.get("section", "")
            section = h.metadata.get("section", "")
            src = h.metadata.get("source", "")
            if not src:
                continue
            # We expand both for data hits AND for narrative/Q&A hits, because
            # narrative chunks of a PQ reply often reference figures that live
            # in sibling annexure tables.
            sources_to_expand[src] = max(sources_to_expand.get(src, 0.0), h.score)

        siblings: list[SearchHit] = []
        for src, parent_score in sources_to_expand.items():
            try:
                res = coll.get(where={"source": src})
            except Exception:
                continue
            added = 0
            for d, m in zip(res.get("documents", []) or [], res.get("metadatas", []) or []):
                section = (m or {}).get("section", "")
                if (src, section) in seen:
                    continue
                # Only attach sibling **data** chunks. Narrative siblings are
                # mostly letterhead and would crowd out useful context.
                if not self._is_data_section(section):
                    continue
                m2 = dict(m or {})
                m2["sibling_of"] = src
                siblings.append(SearchHit(
                    text=d,
                    metadata=m2,
                    score=parent_score * 0.85,
                ))
                seen.add((src, section))
                added += 1
                if added >= max_per_source:
                    break

        combined = primary + siblings
        combined.sort(key=lambda h: h.score, reverse=True)
        return combined[:max_total]

    def stats(self) -> dict:
        return {"pq": self.pq.count(), "db": self.db.count()}


_store: VectorStore | None = None


def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
