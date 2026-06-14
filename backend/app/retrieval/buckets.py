"""Topic buckets — a structured Context → Sources layer over the corpus.

Every chunk is tagged (multi-label) with one or more of the 11 topic buckets
below via boolean metadata flags ``b_<bucket>``. At query time each search tool
routes its own query to the relevant bucket(s) and filters retrieval to them —
but always with a SOFT fallback: if the bucket-scoped search comes back empty or
weak, the tool re-runs unfiltered. So buckets buy precision (topical scoping)
without ever blocking a source, which keeps the "search everything, no
prioritisation" policy intact.

This module is the single source of truth: the bucket list, their descriptors
(embedded into centroids for classification + query routing), their keyword
lexicons, the deterministic file→bucket map for structured tables, and the
human-facing Context→Sources map.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from .vectorstore import VectorStore


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------
BUCKETS: list[str] = [
    "exploration", "drilling", "production", "reserves", "finance",
    "csr", "hr", "hse", "esg", "procurement", "strategy",
]


def flag(bucket: str) -> str:
    """Metadata key for a bucket's boolean flag."""
    return f"b_{bucket}"


# Rich one-line descriptors — embedded once into centroid vectors used for both
# chunk classification and query routing.
BUCKET_DESCRIPTORS: dict[str, str] = {
    "exploration": "Hydrocarbon exploration: exploratory acreage, PEL and PML, OALP HELP DSF blocks and bid rounds, seismic surveys 2D and 3D, sedimentary basins, Andaman, Kerala-Konkan, KG offshore, farm-in, exploration strategy and prospects.",
    "drilling": "Drilling and workover activity: exploratory and development wells drilled, well count, meterage drilled, onshore and offshore rigs, spudding, workover operations in OGPS Assam and Rajasthan.",
    "production": "Production of crude oil and natural gas, LPG and O plus OEG output measured in MMT MMSCM TMT MMTOE, plan versus achievement, with JV and without JV, delivery and sales volumes.",
    "reserves": "Hydrocarbon reserves: proved and probable 1P 2P 3P reserves, reserve accretion, reserve replacement ratio RRR, reserves to production R by P ratio, discoveries, remaining recoverable reserves.",
    "finance": "Financial results: revenue and turnover, profit after tax PAT, EBITDA, profit before tax, dividend, earnings per share EPS, capital expenditure capex, borrowings, net worth, margins and ratios, contribution to exchequer, standalone and consolidated statements.",
    "csr": "Corporate social responsibility CSR: CSR expenditure and obligation, community development projects, beneficiaries, education health drinking water sports and skill projects, CSR committee, Schedule VII activities.",
    "hr": "Human resources and workforce: employee headcount and manpower, executives and workmen, recruitment and hiring, attrition, diversity and women employees, training and apprentices, local employment, employee welfare.",
    "hse": "Health safety and environment: lost time injury frequency rate LTIFR, fatalities, recordable injuries, PPE compliance, safety incidents, occupational health, emergency response, near misses.",
    "esg": "Environment sustainability and governance ESG: greenhouse gas emissions Scope 1 2 3, energy and water consumption, waste, biodiversity, net zero and decarbonisation, ESG ratings, BRSR disclosures, board governance.",
    "procurement": "Procurement and supply chain: vendors and suppliers, MSE and MSME sourcing share, GeM portal procurement, tenders and contracts, payables, local content and indigenisation.",
    "strategy": "Corporate strategy and outlook: Maharatna status, Aspiration 2030 and Vision 2040 targets, subsidiaries NRL Numaligarh and OIL Green Energy, partnerships and joint ventures, energy transition, green hydrogen CBG and renewables, capital projects and acquisitions.",
}

# Keyword lexicon — a fast complementary signal to the embedding centroids.
BUCKET_KEYWORDS: dict[str, list[str]] = {
    "exploration": ["exploration", "exploratory", "oalp", "help", "dsf", " pel", " pml", "seismic", "basin", "andaman", "kerala-konkan", "kg basin", "acreage", "farm-in", "farm in", "prospect"],
    "drilling": ["drilling", "drilled", "well ", "wells", "meterage", "workover", " rig", "rigs", "spud", "ogps"],
    "production": ["production", "produced", "crude oil", "natural gas", "mmscm", " mmt", "lpg", "o+oeg", "mmtoe", "output", "delivery", "with jv", "without jv"],
    "reserves": ["reserve", "reserves", " 2p", " 1p", " 3p", "accretion", "rrr", "reserve replacement", "r/p", "reserves to production", "discovery", "discoveries", "recoverable"],
    "finance": ["revenue", "turnover", "profit", " pat", "ebitda", " pbt", "dividend", " eps", "capex", "capital expenditure", "borrowing", "net worth", "margin", " crore", "exchequer", "standalone", "consolidated", "earnings", "income"],
    "csr": ["csr", "corporate social responsibility", "community", "beneficiar", "schedule vii", "social responsib", "skill development", "drinking water"],
    "hr": ["employee", "headcount", "manpower", "recruit", "attrition", "diversity", "women", "training", "apprentice", "workforce", " staff", "executive", "local employment", "hiring", "welfare"],
    "hse": ["safety", "ltif", "ltifr", "fatalit", "injury", "injuries", " ppe", "incident", "occupational health", "hazard", "accident", "near miss"],
    "esg": ["emission", "scope 1", "scope 2", "scope 3", " ghg", "greenhouse", "energy consumption", "water consumption", "waste", "biodiversity", "net zero", "decarbon", "sustainab", " esg", "brsr", "governance"],
    "procurement": ["procure", "procurement", "vendor", "supplier", " mse", "msme", "gem portal", "tender", "contract", "payable", "local content", "indigenisation", "indigenization"],
    "strategy": ["maharatna", "aspiration 2030", "vision 2040", "strateg", " nrl", "numaligarh", "green energy", "subsidiar", "joint venture", "partnership", "energy transition", "green hydrogen", " cbg", "renewable", "acquisition", "outlook"],
}

# Human-facing Context → Sources map: which source families hold each bucket.
# Documentation + coverage checks; retrieval scopes (not ranks) by bucket.
CONTEXT_SOURCES: dict[str, list[str]] = {
    "exploration": ["PQ", "DOC-RES", "AR (MD&A)"],
    "drilling":    ["XL-DRL", "XL-FY26", "AR"],
    "production":  ["XL-PROD", "XL-FY26", "AR"],
    "reserves":    ["DOC-RES", "XL-PROD", "AR"],
    "finance":     ["AR", "PQ"],
    "csr":         ["PQ", "ESG", "BRSR", "AR (Directors' Report)"],
    "hr":          ["PQ", "BRSR", "ESG", "AR"],
    "hse":         ["ESG", "BRSR", "AR", "PQ"],
    "esg":         ["ESG", "BRSR", "AR"],
    "procurement": ["AR", "BRSR", "PQ"],
    "strategy":    ["AR (MD&A)", "PQ", "ESG"],
}

# Deterministic filename → buckets for the structured tables + synthetic feeds.
STRUCTURED_FILE_BUCKETS: dict[str, list[str]] = {
    "10 Years Production and Reserves Data.xlsx": ["production", "reserves"],
    "FY2025-26 Perforamance.xlsx": ["production", "drilling"],   # note: source's spelling
    "FY2025-26 Performance.xlsx": ["production", "drilling"],
    "Workover & Drilling 5 yrs.xlsx": ["drilling"],
    "Reserves & Discoveries.docx": ["reserves", "exploration"],
    "finance.json": ["finance"],
    "workforce.json": ["hr"],
    "workforce.legacy.json": ["hr"],
    "safety_hr.json": ["hse", "hr"],
    "procurement.json": ["procurement"],
    "ppe_events.json": ["hse"],
}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _centroids() -> np.ndarray:
    """(len(BUCKETS), dim) matrix of normalised descriptor embeddings."""
    emb = VectorStore.embedder()
    vecs = emb.encode(
        [BUCKET_DESCRIPTORS[b] for b in BUCKETS],
        normalize_embeddings=True, show_progress_bar=False,
    )
    return np.asarray(vecs, dtype=np.float32)


def _keyword_hits(text_lower: str) -> dict[str, int]:
    return {b: sum(1 for kw in kws if kw in text_lower) for b, kws in BUCKET_KEYWORDS.items()}


def _scores(text: str, embedding=None) -> dict[str, float]:
    """Combined per-bucket score = cosine(centroid) + small keyword nudge.

    `embedding` (a normalised vector, e.g. fetched from Chroma) lets the backfill
    score chunks without re-embedding. When omitted we embed the text here.
    """
    if not text or not text.strip():
        return {b: 0.0 for b in BUCKETS}
    if embedding is None:
        embedding = VectorStore.embedder().encode([text], normalize_embeddings=True)[0]
    emb = np.asarray(embedding, dtype=np.float32)
    n = float(np.linalg.norm(emb))
    if n > 0:
        emb = emb / n
    sims = _centroids() @ emb   # cosine, since both normalised
    kw = _keyword_hits(text.lower())
    kw_max = max(kw.values()) or 1
    return {b: float(sims[i]) + 0.12 * (kw[b] / kw_max) for i, b in enumerate(BUCKETS)}


def classify_text(text: str, embedding=None, *, margin: float = 0.06, abs_floor: float = 0.18, max_buckets: int = 3) -> list[str]:
    """Multi-label classify a CHUNK into buckets. Always returns ≥1 bucket
    (the top one) so every chunk is reachable by a bucket-scoped search."""
    sc = _scores(text, embedding)
    top_b = max(sc, key=sc.get)
    top = sc[top_b]
    picked = [b for b in BUCKETS if sc[b] >= max(abs_floor, top - margin)]
    # strong keyword evidence pulls a bucket in even if the centroid is lukewarm
    kw = _keyword_hits((text or "").lower())
    for b in BUCKETS:
        if kw[b] >= 2 and b not in picked:
            picked.append(b)
    picked = sorted(picked, key=lambda b: sc[b], reverse=True)[:max_buckets]
    return picked or [top_b]


def route_query(query: str, *, confidence: float = 0.30, margin: float = 0.08, max_buckets: int = 4) -> list[str]:
    """Route a QUERY to bucket(s). Returns [] when the signal is weak — the
    caller treats [] as "search everything" (soft fallback)."""
    sc = _scores(query)
    top = max(sc.values()) if sc else 0.0
    if top < confidence:
        return []                      # not confident → search all buckets
    picked = [b for b in BUCKETS if sc[b] >= top - margin]
    return sorted(picked, key=lambda b: sc[b], reverse=True)[:max_buckets]


# ---------------------------------------------------------------------------
# Tagging helpers (used by ingest + backfill)
# ---------------------------------------------------------------------------
def buckets_for_file(filename: str, source: str = "") -> list[str] | None:
    """Deterministic buckets for a structured/known file, or None if the file's
    chunks should be classified by content instead (narrative reports)."""
    if filename in STRUCTURED_FILE_BUCKETS:
        return list(STRUCTURED_FILE_BUCKETS[filename])
    return None


def apply_bucket_flags(meta: dict, buckets: list[str]) -> dict:
    """Write all 11 b_<bucket> boolean flags + a readable `buckets` string onto
    a metadata dict (mutates and returns it). Every flag is set explicitly
    (True/False) so re-running the backfill correctly flips stale tags and the
    `$or` filters stay uniform across chunks."""
    sel = {b for b in buckets if b in BUCKETS}
    for b in BUCKETS:
        meta[flag(b)] = b in sel
    meta["buckets"] = ",".join(b for b in BUCKETS if b in sel)
    return meta
