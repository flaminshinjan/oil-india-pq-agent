"""Dynamic HR / HSE / Procurement / Finance fact extraction.

The dashboards used to read from a hand-curated JSON in
`data/disclosures/`.  Per user feedback those values must come straight
from OIL's corpus — Annual Reports, BRSR, ESG Data Books — at runtime.

This module:
  1. Pulls relevant chunks from Chroma per metric family (RAG).
  2. Hands them to Anthropic with a strict JSON schema.
  3. Caches the result for the lifetime of the process (TTL via the
     `_TTL_SECS` knob).
  4. Falls back to the JSON file if Anthropic / Chroma is unavailable
     so the dashboards never go blank.

Each `extract_*()` function returns the same shape as the JSON file it
replaces, so the metrics functions can swap data source transparently.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from loguru import logger

from ..config import settings
from ..retrieval.vectorstore import get_store


_TTL_SECS = 60 * 60 * 6        # cache extracted facts for 6 hours
_DISCLOSURES_DIR = Path(__file__).resolve().parents[2] / "data" / "disclosures"
_CACHE: dict[str, tuple[float, dict]] = {}


def _client():
    """Lazy-import Anthropic so the rest of the app loads even if the
    SDK is missing (Pipecat pinning sometimes drifts)."""
    try:
        from anthropic import Anthropic
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[dynamic_extract] anthropic SDK unavailable: {exc}")
        return None
    return Anthropic(api_key=settings.anthropic_api_key)


def _fallback(name: str) -> dict:
    """Read the curated JSON fallback. Never raises."""
    path = _DISCLOSURES_DIR / f"{name}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[dynamic_extract] {name} fallback read failed: {exc}")
        return {}


def _gather_context(queries: list[str], collection: str = "pq",
                    per_q: int = 4, max_chars: int = 14_000) -> str:
    """Run several semantic queries against Chroma and concatenate the
    distinct excerpts. Synthetic JSON files are excluded."""
    store = get_store()
    seen: set[tuple] = set()
    chunks: list[str] = []
    used = 0
    for q in queries:
        try:
            hits = store.search(collection, q, k=per_q)
        except Exception:  # noqa: BLE001
            continue
        for h in hits:
            md = h.metadata or {}
            fname = md.get("filename") or ""
            if fname.endswith(".json"):
                continue
            ident = (fname, md.get("section"))
            if ident in seen:
                continue
            seen.add(ident)
            piece = f"[{fname} – {md.get('section') or 'narrative'}]\n{(h.text or '').strip()[:1100]}"
            if used + len(piece) > max_chars:
                break
            chunks.append(piece)
            used += len(piece)
    return "\n\n---\n\n".join(chunks)


def _extract_json(prompt: str, max_tokens: int = 3000) -> dict | None:
    """Send the prompt to Anthropic, parse a JSON object out of the
    response. Tolerates surrounding markdown fences."""
    client = _client()
    if client is None:
        return None
    try:
        resp = client.messages.create(
            model=os.getenv("ANTHROPIC_EXTRACT_MODEL", "claude-haiku-4-5-20251001"),
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text  # type: ignore[index]
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[dynamic_extract] anthropic call failed: {exc}")
        return None

    text = (text or "").strip()
    # Strip code fences.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    # Some models prepend prose; try to slice the first { … last }.
    if "{" in text and "}" in text:
        text = text[text.index("{") : text.rindex("}") + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning(f"[dynamic_extract] JSON parse failed: {exc}; snippet: {text[:200]}")
        return None


def _deep_merge(base: Any, extra: Any) -> Any:
    """Merge `extra` over `base` without letting null / empty / placeholder
    values in `extra` clobber concrete values in `base`. Lists of dicts
    are merged element-wise on common keys (e.g. `fy`)."""
    if extra is None:
        return base
    if isinstance(base, dict) and isinstance(extra, dict):
        out = dict(base)
        for k, v in extra.items():
            out[k] = _deep_merge(base.get(k), v)
        return out
    if isinstance(base, list) and isinstance(extra, list):
        # Try to merge by `fy` if both are lists of dicts with that key.
        if base and isinstance(base[0], dict) and "fy" in base[0]:
            by_fy = {r.get("fy"): dict(r) for r in base if isinstance(r, dict)}
            for r in extra:
                if not isinstance(r, dict):
                    continue
                fy = r.get("fy")
                if fy is None:
                    continue
                if fy in by_fy:
                    by_fy[fy] = _deep_merge(by_fy[fy], r)
                else:
                    by_fy[fy] = r
            return [v for k, v in sorted(by_fy.items()) if v]
        # Otherwise: prefer `extra` if non-empty.
        return extra if extra else base
    # Scalars — only override base if extra is meaningful.
    if extra in (None, "", [], {}):
        return base
    return extra


def _cached(name: str, build) -> dict:
    """Cache `name` → dict for `_TTL_SECS`. `build()` is called only on miss."""
    now = time.time()
    hit = _CACHE.get(name)
    if hit and (now - hit[0]) < _TTL_SECS:
        return hit[1]
    try:
        data = build() or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[dynamic_extract] build({name}) failed: {exc}")
        data = {}
    # Deep-merge the LLM-extracted facts over the curated JSON. Nulls
    # / blanks in the extracted payload never clobber a known value.
    merged = _deep_merge(_fallback(name), data if isinstance(data, dict) else {})
    _CACHE[name] = (now, merged)
    return merged


def reset_cache() -> None:
    """Drop the cache — called by /api/os/refresh-disclosures."""
    _CACHE.clear()


# ============================================================
# HR
# ============================================================

_HR_QUERIES = [
    "total headcount employees executives workers permanent BRSR FY 2024-25 2023-24",
    "women female workforce diversity percent share management",
    "attrition turnover rate male female employees workers",
    "training hours per employee FTE skills upgradation",
    "apprentices count engaged trade",
    "scheduled caste tribe OBC minority person disability workforce",
    "POSH sexual harassment complaints upheld",
    "engagement survey participation score employees first ever",
]

_HR_SCHEMA = """{
  "headcount_5yr": [{"fy": "YYYY-YY", "total": int, "executives": int, "workers": int}],
  "women_pct_5yr": [{"fy": "YYYY-YY", "pct": float}],
  "diversity_fy24": {
    "women_pct_workforce": float,
    "women_pct_workforce_fy25": float,
    "women_pct_all_management": float,
    "women_pct_junior_management": float,
    "women_pct_top_management": float,
    "women_pct_stem": float
  },
  "reservation_fy24": [{"category": str, "workforce_pct": float, "management_pct": float}],
  "training_fy24": {
    "executives_total": int,
    "executives_trained": int,
    "executives_participation_pct": float,
    "workers_total": int,
    "workers_trained": int,
    "workers_participation_pct": float,
    "avg_spend_per_employee_inr": int
  },
  "training_intensity_5yr": [{"fy": "YYYY-YY", "hours_per_employee": float}],
  "turnover_pct_5yr": [{"fy": "YYYY-YY", "total": float, "voluntary": float}],
  "apprentices_5yr": [{"fy": "YYYY-YY", "count": int}],
  "posh_complaints_3yr": [{"fy": "YYYY-YY", "filed": int, "upheld": int, "pending": int}],
  "engagement_survey_fy25": {"participation_pct": float, "score": float, "note": str}
}"""


def _build_hr() -> dict | None:
    context = _gather_context(_HR_QUERIES, collection="pq")
    if not context:
        return None
    prompt = (
        "You are extracting structured HR facts from OIL India's BRSR / "
        "ESG / Annual-Report excerpts below. Return JSON ONLY — no prose, "
        "no markdown.\n\n"
        f"Schema (use null where a value isn't in the excerpts):\n{_HR_SCHEMA}\n\n"
        f"Excerpts:\n{context}\n\n"
        "Return JSON ONLY."
    )
    return _extract_json(prompt, max_tokens=3500)


def extract_hr() -> dict:
    return _cached("workforce", _build_hr)


# ============================================================
# HSE
# ============================================================

_HSE_QUERIES = [
    "LTIFR lost time injury frequency rate workers executives BRSR per million",
    "fatalities high consequence recordable injuries workers employees",
    "HSE training participants executives workers contractors apprentices",
    "ISO 45001 IMS integrated management system 9001 14001 OIL",
    "Project KAVACH Zero Tolerance Policy Stop Work Authority safety",
    "near miss reports hazard 5 star work environment",
]

_HSE_SCHEMA = """{
  "ltifr_5yr": [{"fy": "YYYY-YY", "overall": float|null, "executives": float|null, "workers": float|null}],
  "incidents_5yr": [{
    "fy": "YYYY-YY",
    "recordable_workers": int,
    "recordable_executives": int,
    "high_consequence_workers": int,
    "high_consequence_executives": int,
    "fatalities_workers": int,
    "fatalities_executives": int,
    "man_days_lost": int|null
  }],
  "hse_training_participants_5yr": [{
    "fy": "YYYY-YY",
    "executives": int|null,
    "workers": int|null,
    "contractors": int|null,
    "apprentices": int|null
  }],
  "iso_certification": {"status_fy25": str, "completion_fy": "YYYY-YY", "scope": str},
  "key_interventions": [{"fy": "YYYY-YY", "name": str, "description": str}],
  "headlines_fy25": [str]
}"""


def _build_hse() -> dict | None:
    context = _gather_context(_HSE_QUERIES, collection="pq")
    if not context:
        return None
    prompt = (
        "You are extracting structured HSE / safety facts from OIL India's "
        "BRSR / ESG / Annual-Report excerpts below. Return JSON ONLY — "
        "no prose, no markdown.\n\n"
        f"Schema (use null / empty arrays where data isn't disclosed):\n{_HSE_SCHEMA}\n\n"
        f"Excerpts:\n{context}\n\n"
        "Return JSON ONLY."
    )
    return _extract_json(prompt, max_tokens=3500)


def extract_hse() -> dict:
    return _cached("safety_hr", _build_hse)
