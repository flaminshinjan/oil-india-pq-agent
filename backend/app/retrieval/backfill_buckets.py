"""Backfill topic-bucket tags onto an already-ingested Chroma store.

Reuses the chunks' STORED embeddings to classify them — no re-embedding — and
updates only their metadata (the b_<bucket> flags + a readable `buckets`
string). Idempotent: re-running re-classifies and overwrites the flags.

Run:  python -m app.retrieval.backfill_buckets          (tag + report)
      python -m app.retrieval.backfill_buckets --report  (report only, no write)
"""
from __future__ import annotations

import argparse
from collections import Counter

from .buckets import BUCKETS, apply_bucket_flags, buckets_for_file, classify_text
from .vectorstore import get_store


def _classify_chunk(doc: str, meta: dict, embedding) -> list[str]:
    """Deterministic buckets for structured files; else classify by content
    using the stored embedding (no re-embed)."""
    fb = buckets_for_file(meta.get("filename", ""), meta.get("source", ""))
    if fb is not None:
        return fb
    return classify_text(doc or "", embedding=embedding)


def backfill(*, write: bool = True, batch: int = 256) -> dict:
    store = get_store()
    report: dict[str, Counter] = {}

    for name, coll in (("pq", store.pq), ("db", store.db)):
        res = coll.get(include=["documents", "metadatas", "embeddings"])
        ids = res.get("ids")
        ids = list(ids) if ids is not None else []
        docs = res.get("documents")
        docs = list(docs) if docs is not None else []
        metas = res.get("metadatas")
        metas = list(metas) if metas is not None else []
        embs = res.get("embeddings")
        embs = list(embs) if embs is not None else []
        counts: Counter = Counter()
        per_file: dict[str, Counter] = {}

        upd_ids: list[str] = []
        upd_metas: list[dict] = []
        for i, _id in enumerate(ids):
            doc = docs[i] if i < len(docs) else ""
            meta = dict(metas[i] or {})
            emb = embs[i] if i < len(embs) else None
            bks = _classify_chunk(doc, meta, emb)
            apply_bucket_flags(meta, bks)
            for b in bks:
                counts[b] += 1
            fn = meta.get("filename", "?")
            per_file.setdefault(fn, Counter()).update(bks)
            upd_ids.append(_id)
            upd_metas.append(meta)

        if write and upd_ids:
            for j in range(0, len(upd_ids), batch):
                coll.update(ids=upd_ids[j:j + batch], metadatas=upd_metas[j:j + batch])

        report[name] = counts
        # ---- print collection report ----
        total = len(ids)
        print(f"\n=== {name} collection — {total} chunks ===")
        for b in BUCKETS:
            c = counts.get(b, 0)
            bar = "█" * int(40 * c / max(total, 1))
            print(f"  {b:12} {c:6}  {bar}")
        # per-file bucket spread (helps catch a mis-mapped structured file)
        print(f"  -- per-file dominant buckets --")
        for fn in sorted(per_file):
            top = ", ".join(f"{b}:{n}" for b, n in per_file[fn].most_common(3))
            print(f"     {fn[:46]:48} {top}")

    if not write:
        print("\n[report only — no metadata written]")
    else:
        print("\n[backfill complete — bucket flags written]")
    return {k: dict(v) for k, v in report.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="classify + print distribution, do NOT write")
    args = ap.parse_args()
    backfill(write=not args.report)


if __name__ == "__main__":
    main()
