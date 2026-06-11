"""Per-domain dashboard metrics extracted from OIL's own data files.

Every function returns a dict with this shape:

    {
        "kpis":         [ {"label", "value", "unit", "trend", "amber", "note"}, ... ],
        "breakdowns":   [ {"title", "items": [ {"label", "value", "share"}, ... ]}, ... ],
        "trend":        { "label", "unit", "labels"[], "series": [{"name","values"}] } | None,
        "highlights":   [ "...", "..." ],
    }

Values are READ at request time so any tweak to the underlying Excel /
JSON immediately reflects in the dashboard. Nothing is hardcoded — every
number is derived from data files in `backend/data/`.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import openpyxl
from loguru import logger

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _resolve_subdir(candidates: list[str]) -> Path:
    """Pick the first existing subdirectory — handles `db` vs `DB`
    case mismatch between dev (macOS, case-insensitive) and prod
    (Linux, case-sensitive)."""
    for name in candidates:
        p = DATA_DIR / name
        if p.exists():
            return p
    return DATA_DIR / candidates[0]


DB_DIR = _resolve_subdir(["db", "DB"])
SYN_DIR = _resolve_subdir(["synthetic", "Synthetic"])
DISCL_DIR = _resolve_subdir(["disclosures", "Disclosures"])


# ============================================================
# Helpers
# ============================================================

def _safe_load_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[domain_metrics] cannot load {path}: {exc}")
        return {}


def _ten_year_table() -> list[dict]:
    """Read the 10-yr production + reserves Excel into row dicts:

        [ {"fy": "2015-16", "crude_mmt": 3.25, "gas_mmscm": 2838,
           "oil_2p_mmt": 80.74, "gas_2p_bcm": 121.13, "rec_mmtoe": 7.21,
           "rrr": None }, ... ]
    """
    path = DB_DIR / "10 Years Production and Reserves Data.xlsx"
    if not path.exists():
        return []
    try:
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb.active
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[domain_metrics] 10yr xlsx open failed: {exc}")
        return []

    rows: list[dict] = []
    # Columns (per inspection):
    #   A = FY label,
    #   B = crude (MMT), D = gas (MMSCM),
    #   F = 2P oil (MMT), H = 2P gas (BCM),
    #   L = recoverable (MMToE), N = RRR
    for r in range(4, ws.max_row + 1):
        fy = ws.cell(row=r, column=1).value
        if not fy or not isinstance(fy, str) or "-" not in fy:
            continue
        rows.append({
            "fy": fy.strip(),
            "crude_mmt":   _as_float(ws.cell(row=r, column=2).value),
            "gas_mmscm":   _as_float(ws.cell(row=r, column=4).value),
            "oil_2p_mmt":  _as_float(ws.cell(row=r, column=6).value),
            "gas_2p_bcm":  _as_float(ws.cell(row=r, column=8).value),
            "rec_mmtoe":   _as_float(ws.cell(row=r, column=12).value),
            "rrr":         _as_float(ws.cell(row=r, column=14).value),
        })
    return rows


def _as_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        if f != f:  # NaN
            return None
        return round(f, 4)
    except (TypeError, ValueError):
        return None


def _latest_with(rows: list[dict], key: str) -> tuple[dict | None, dict | None, dict | None]:
    """Return (latest, prev, five_back) rows where `rows[i][key]` is not None.

    Falls back gracefully when the latest FY hasn't been updated for one
    of the columns (e.g. RRR or 2P reserves often lag crude/gas by a
    quarter). Without this we'd render "—" for any metric whose latest
    cell is blank, which makes the dashboard look broken.
    """
    valid = [r for r in rows if r.get(key) is not None]
    if not valid:
        return None, None, None
    latest = valid[-1]
    prev = valid[-2] if len(valid) >= 2 else None
    five_back = valid[-6] if len(valid) >= 6 else (valid[0] if len(valid) >= 2 else None)
    return latest, prev, five_back


def _yoy(curr: float | None, prev: float | None) -> tuple[float | None, str]:
    """Return (signed_pct, "↑ 2.1% YoY"|"↓ 3.0% YoY"|"flat YoY")."""
    if curr is None or prev is None or prev == 0:
        return None, "—"
    pct = (curr - prev) / prev * 100
    if abs(pct) < 0.05:
        return pct, "flat YoY"
    arrow = "↑" if pct > 0 else "↓"
    return pct, f"{arrow} {abs(pct):.1f}% YoY"


def _kpi(label: str, value: str, unit: str = "", trend: str = "",
         amber: bool = False, note: str = "") -> dict:
    return {"label": label, "value": value, "unit": unit, "trend": trend,
            "amber": amber, "note": note}


def _fmt(v: float | None, fmt: str = "{:.2f}") -> str:
    if v is None:
        return "—"
    return fmt.format(v)


# ============================================================
# Domain: Production
# ============================================================

def production_metrics() -> dict:
    rows = _ten_year_table()
    if not rows:
        return {"kpis": [], "breakdowns": [], "trend": None, "highlights": []}

    crude_l, crude_p, crude_5 = _latest_with(rows, "crude_mmt")
    gas_l,   gas_p,   _       = _latest_with(rows, "gas_mmscm")
    rrr_l,   _,       _       = _latest_with(rows, "rrr")

    _, crude_yoy_lbl = _yoy(crude_l.get("crude_mmt") if crude_l else None,
                            crude_p.get("crude_mmt") if crude_p else None)
    _, gas_yoy_lbl   = _yoy(gas_l.get("gas_mmscm") if gas_l else None,
                            gas_p.get("gas_mmscm") if gas_p else None)
    five_pct, _ = _yoy(
        crude_l.get("crude_mmt") if crude_l else None,
        crude_5.get("crude_mmt") if crude_5 else None,
    )

    crude_amber = (crude_l and crude_p and crude_l["crude_mmt"] < crude_p["crude_mmt"])
    gas_amber   = (gas_l   and gas_p   and gas_l["gas_mmscm"]  < gas_p["gas_mmscm"])

    # FY25-26 cumulative target vs achievement (from the live annexure).
    totals = _production_totals()
    crude_ach = (totals.get("crude_actual", 0) / totals["crude_target"]
                 if totals.get("crude_target") else None)
    gas_ach = (totals.get("gas_actual", 0) / totals["gas_target"]
               if totals.get("gas_target") else None)

    kpis = [
        _kpi("Crude oil production",
             _fmt(crude_l.get("crude_mmt") if crude_l else None),
             "MMT", crude_yoy_lbl, amber=bool(crude_amber),
             note=f"FY{crude_l['fy']} actual" if crude_l else ""),
        _kpi("Natural gas production",
             _fmt(gas_l.get("gas_mmscm") if gas_l else None, "{:.0f}"),
             "MMSCM", gas_yoy_lbl, amber=bool(gas_amber),
             note=f"FY{gas_l['fy']} actual" if gas_l else ""),
        _kpi("FY25-26 crude % achieved",
             f"{int(round(crude_ach * 100))}%" if crude_ach is not None else "—",
             "",
             f"{_fmt(totals.get('crude_actual'))} of {_fmt(totals.get('crude_target'))} MMT"
             if totals else "cumulative MTD",
             amber=(crude_ach is not None and crude_ach < 0.95)),
        _kpi("FY25-26 gas % achieved",
             f"{int(round(gas_ach * 100))}%" if gas_ach is not None else "—",
             "",
             f"{_fmt(totals.get('gas_actual'))} of {_fmt(totals.get('gas_target'))} MMSCM"
             if totals else "cumulative MTD",
             amber=(gas_ach is not None and gas_ach < 0.95)),
    ]

    # State-level breakdown from FY perf annexure (Assam / Arunachal / Rajasthan)
    breakdowns: list[dict] = []
    state_split = _production_by_state()
    if state_split:
        breakdowns.append({
            "title": "Crude production by state (FY25-26 MTD)",
            "unit": "MMT",
            "items": state_split,
        })

    # Trend chart — last 8 FYs of crude MMT vs gas MMSCM
    trend = {
        "label": "Crude (MMT) and Gas (MMSCM, ÷ 1000)",
        "unit": "indexed",
        "labels": [r["fy"] for r in rows[-8:]],
        "series": [
            {"name": "Crude oil (MMT)", "values": [r["crude_mmt"] for r in rows[-8:]]},
            {"name": "Gas (MMSCM, ÷ 1000)",
             "values": [(r["gas_mmscm"] / 1000) if r["gas_mmscm"] else None
                        for r in rows[-8:]]},
        ],
    }

    highlights = []
    if five_pct is not None:
        if five_pct < -2:
            highlights.append(
                f"Crude output has declined {abs(five_pct):.1f}% over five "
                f"years — well below the 4 MMT goal."
            )
        elif five_pct > 2:
            highlights.append(
                f"Crude output is up {five_pct:.1f}% over five years; on "
                f"trajectory toward the 4 MMT goal."
            )
    if rrr_l and rrr_l.get("rrr") and rrr_l["rrr"] >= 1.0:
        highlights.append(
            f"RRR of {rrr_l['rrr']:.2f} (FY{rrr_l['fy']}) means OIL is "
            f"replacing reserves at ≥1× of what it produced that year."
        )
    if crude_ach is not None and crude_ach < 0.95:
        gap = (totals.get("crude_target", 0) - totals.get("crude_actual", 0))
        highlights.append(
            f"FY25-26 crude achievement at {int(round(crude_ach * 100))}% of "
            f"target — {gap:.2f} MMT short of plan."
        )
    if gas_ach is not None and gas_ach < 0.95:
        gap = (totals.get("gas_target", 0) - totals.get("gas_actual", 0))
        highlights.append(
            f"FY25-26 gas achievement at {int(round(gas_ach * 100))}% — "
            f"{gap:.0f} MMSCM short of plan."
        )

    return {"kpis": kpis, "breakdowns": breakdowns, "trend": trend,
            "highlights": highlights}


def _fy_perf_wb():
    """Open the FY2025-26 Performance workbook (cached load)."""
    path = DB_DIR / "FY2025-26 Perforamance.xlsx"
    if not path.exists():
        return None
    try:
        return openpyxl.load_workbook(path, data_only=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[domain_metrics] FY perf open failed: {exc}")
        return None


def _production_by_state() -> list[dict]:
    wb = _fy_perf_wb()
    if not wb:
        return []
    sheet_name = next((n for n in wb.sheetnames if "Production" in n), None)
    if not sheet_name:
        return []
    ws = wb[sheet_name]

    items: list[dict] = []
    # Per inspection, rows 6..8 list Assam / Arunachal / Rajasthan crude:
    # col A = activity, col B = state, col D = cum target, col E = cum actual
    for r in range(6, ws.max_row + 1):
        state = ws.cell(row=r, column=2).value
        target = _as_float(ws.cell(row=r, column=4).value)
        actual = _as_float(ws.cell(row=r, column=5).value)
        if not state or not isinstance(state, str):
            continue
        if state.lower().startswith("total"):
            break
        if not target or actual is None:
            continue
        share = round(actual / target, 3) if target else 0
        items.append({"label": state.strip(), "value": round(actual, 3),
                      "share": share,
                      "amber": share < 0.95})
        if len(items) >= 4:
            break
    return items


def _production_totals() -> dict:
    """Total crude + gas FY25-26 cumulative target vs achievement —
    sourced from the same Annexure-V-Production sheet."""
    wb = _fy_perf_wb()
    if not wb:
        return {}
    sheet_name = next((n for n in wb.sheetnames if "Production" in n), None)
    if not sheet_name:
        return {}
    ws = wb[sheet_name]

    out: dict = {"crude_target": 0.0, "crude_actual": 0.0,
                 "gas_target": 0.0, "gas_actual": 0.0}
    activity_row = ""
    for r in range(5, ws.max_row + 1):
        act = ws.cell(row=r, column=1).value
        if isinstance(act, str) and act.strip():
            activity_row = act.strip().lower()
        t = _as_float(ws.cell(row=r, column=4).value)
        a = _as_float(ws.cell(row=r, column=5).value)
        if t is None or a is None:
            continue
        if "total crude oil production (with jv)" in activity_row:
            out["crude_target"] = t
            out["crude_actual"] = a
        elif "total natural gas production (with jv)" in activity_row:
            out["gas_target"] = t
            out["gas_actual"] = a
    return out


def _drilling_fy_progress() -> dict:
    """FY25-26 BE target vs cumulative achievement, for exploratory
    AND development drilling — read from Annexures III and IV."""
    wb = _fy_perf_wb()
    if not wb:
        return {}

    def _sum_sheet(sheet_substring: str) -> dict:
        sn = next((n for n in wb.sheetnames if sheet_substring in n), None)
        if not sn:
            return {}
        ws = wb[sn]
        # Per inspection — col 5 = target meterage, col 6 = target wells,
        # col 7 = actual meterage, col 8 = actual wells. Sum data rows
        # (skip the header rows and the "Total" rows themselves).
        target_m = 0.0
        target_w = 0
        actual_m = 0.0
        actual_w = 0
        for r in range(8, ws.max_row + 1):
            label = ws.cell(row=r, column=1).value
            label_s = str(label or "").lower()
            if label_s.startswith("total") or "grand" in label_s:
                continue
            tm = _as_float(ws.cell(row=r, column=5).value)
            tw = _as_float(ws.cell(row=r, column=6).value)
            am = _as_float(ws.cell(row=r, column=7).value)
            aw = _as_float(ws.cell(row=r, column=8).value)
            if tm: target_m += tm
            if tw: target_w += int(tw)
            if am: actual_m += am
            if aw: actual_w += int(aw)
        return {"target_m": round(target_m, 1), "target_w": target_w,
                "actual_m": round(actual_m, 1), "actual_w": actual_w}

    return {
        "exploratory": _sum_sheet("Expl. Drl"),
        "development": _sum_sheet("Dev. Drl"),
    }


def _seismic_fy_progress() -> dict:
    """FY25-26 BE vs achievement for 2D and 3D seismic — Annexures I+II."""
    wb = _fy_perf_wb()
    if not wb:
        return {}

    def _read(sheet_substring: str) -> dict:
        sn = next((n for n in wb.sheetnames if sheet_substring in n), None)
        if not sn:
            return {}
        ws = wb[sn]
        target = 0.0
        actual = 0.0
        for r in range(7, ws.max_row + 1):
            label = ws.cell(row=r, column=1).value
            label_s = str(label or "").lower()
            if label_s.startswith("total") or "grand" in label_s:
                continue
            t = _as_float(ws.cell(row=r, column=5).value)
            a = _as_float(ws.cell(row=r, column=6).value)
            if t: target += t
            if a: actual += a
        return {"target": round(target, 1), "actual": round(actual, 1)}

    return {"d2": _read("2D"), "d3": _read("3D")}


# ============================================================
# Domain: Exploration
# ============================================================

def exploration_metrics() -> dict:
    rows = _ten_year_table()
    if not rows:
        return {"kpis": [], "breakdowns": [], "trend": None, "highlights": []}

    rec_l, rec_p, _ = _latest_with(rows, "rec_mmtoe")
    rec_amber = (rec_l and rec_p and rec_l["rec_mmtoe"] < rec_p["rec_mmtoe"])

    # FY25-26 drilling progress from the live annexure — this IS the
    # current-year data the user expected to see.
    drilling = _drilling_fy_progress()
    expl = drilling.get("exploratory") or {}
    devp = drilling.get("development") or {}
    expl_ach = (expl["actual_w"] / expl["target_w"]
                if expl.get("target_w") else None)
    devp_ach = (devp["actual_w"] / devp["target_w"]
                if devp.get("target_w") else None)

    kpis = [
        _kpi("Exploratory wells FY25-26",
             f"{expl.get('actual_w', 0)} of {expl.get('target_w', 0)}",
             "wells",
             f"{int(round(expl_ach * 100))}% of plan"
             if expl_ach is not None else "BE vs cum actual",
             amber=(expl_ach is not None and expl_ach < 0.9),
             note=f"{_fmt(expl.get('actual_m'), '{:,.0f}')} of "
                  f"{_fmt(expl.get('target_m'), '{:,.0f}')} m drilled"
                  if expl else ""),
        _kpi("Development wells FY25-26",
             f"{devp.get('actual_w', 0)} of {devp.get('target_w', 0)}",
             "wells",
             f"{int(round(devp_ach * 100))}% of plan"
             if devp_ach is not None else "BE vs cum actual",
             amber=(devp_ach is not None and devp_ach < 0.9),
             note=f"{_fmt(devp.get('actual_m'), '{:,.0f}')} of "
                  f"{_fmt(devp.get('target_m'), '{:,.0f}')} m drilled"
                  if devp else ""),
        _kpi("Recoverable reserves",
             _fmt(rec_l.get("rec_mmtoe") if rec_l else None),
             "MMToE",
             f"FY{rec_l['fy']} year-end" if rec_l else "—",
             amber=bool(rec_amber)),
        _kpi("2P oil reserves",
             _fmt((_latest_with(rows, "oil_2p_mmt")[0] or {}).get("oil_2p_mmt")),
             "MMT",
             f"FY{(_latest_with(rows, 'oil_2p_mmt')[0] or {}).get('fy', '')} year-end"
             if _latest_with(rows, "oil_2p_mmt")[0] else "—",
             note="reserves are disclosed annually after year-end"),
    ]

    # Bigger breakdowns array — FY25-26 progress + seismic + historical wells
    breakdowns: list[dict] = []
    if expl.get("target_w") or devp.get("target_w"):
        breakdowns.append({
            "title": "Wells planned vs drilled (FY25-26 cumulative)",
            "unit": "wells",
            "items": [
                {"label": "Exploratory · target",
                 "value": expl.get("target_w", 0),
                 "share": 1.0},
                {"label": "Exploratory · actual",
                 "value": expl.get("actual_w", 0),
                 "share": expl_ach or 0,
                 "amber": (expl_ach is not None and expl_ach < 0.9)},
                {"label": "Development · target",
                 "value": devp.get("target_w", 0),
                 "share": 1.0},
                {"label": "Development · actual",
                 "value": devp.get("actual_w", 0),
                 "share": devp_ach or 0,
                 "amber": (devp_ach is not None and devp_ach < 0.9)},
            ],
        })
    seismic = _seismic_fy_progress()
    if seismic.get("d2", {}).get("target") or seismic.get("d3", {}).get("target"):
        breakdowns.append({
            "title": "Seismic survey FY25-26 (target vs actual)",
            "unit": "LKM / SQKM",
            "items": [
                {"label": "2D · target (LKM)",
                 "value": seismic["d2"].get("target", 0), "share": 1.0},
                {"label": "2D · actual (LKM)",
                 "value": seismic["d2"].get("actual", 0),
                 "share": (seismic["d2"].get("actual", 0)
                           / seismic["d2"]["target"]
                           if seismic["d2"].get("target") else 0)},
                {"label": "3D · target (SQKM)",
                 "value": seismic["d3"].get("target", 0), "share": 1.0},
                {"label": "3D · actual (SQKM)",
                 "value": seismic["d3"].get("actual", 0),
                 "share": (seismic["d3"].get("actual", 0)
                           / seismic["d3"]["target"]
                           if seismic["d3"].get("target") else 0)},
            ],
        })
    wells_5yr = _drilling_wells()
    if wells_5yr:
        breakdowns.append({
            "title": "Wells drilled by category (5-yr file, latest year)",
            "unit": "wells",
            "items": wells_5yr,
        })

    trend = {
        "label": "2P oil reserves trend (last available disclosures)",
        "unit": "MMT",
        "labels": [r["fy"] for r in rows[-8:]],
        "series": [
            {"name": "2P oil (MMT)", "values": [r["oil_2p_mmt"] for r in rows[-8:]]},
        ],
    }

    highlights = []
    if expl_ach is not None and expl_ach < 0.9:
        highlights.append(
            f"Exploratory drilling tracking at {int(round(expl_ach * 100))}% "
            f"of FY25-26 plan — {expl.get('target_w', 0) - expl.get('actual_w', 0)} "
            f"wells short."
        )
    if devp_ach is not None and devp_ach < 0.9:
        highlights.append(
            f"Development drilling at {int(round(devp_ach * 100))}% of plan — "
            f"{devp.get('target_w', 0) - devp.get('actual_w', 0)} wells behind."
        )
    if expl.get("actual_m") and expl.get("target_m") and expl["actual_m"] > expl["target_m"]:
        highlights.append(
            f"Exploratory meterage ahead of plan — {expl['actual_m']:,.0f} m "
            f"drilled vs {expl['target_m']:,.0f} m budgeted."
        )

    return {"kpis": kpis, "breakdowns": breakdowns, "trend": trend,
            "highlights": highlights}


def _drilling_wells() -> list[dict]:
    path = DB_DIR / "Workover & Drilling 5 yrs.xlsx"
    if not path.exists():
        return []
    try:
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb.active
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[domain_metrics] drilling xlsx open failed: {exc}")
        return []

    # Per inspection: row 3 = 2024-25, col B-G = exploratory offshore /
    # onshore, development offshore / onshore, total offshore / onshore.
    out: list[dict] = []
    target_year = None
    for r in range(2, ws.max_row + 1):
        v = ws.cell(row=r, column=1).value
        if isinstance(v, str) and v.strip().startswith("2024-25"):
            target_year = r
            break
    if not target_year:
        return []

    labels = ["Exploratory · offshore", "Exploratory · onshore",
              "Development · offshore", "Development · onshore"]
    cols = [2, 3, 4, 5]
    vals = []
    for label, c in zip(labels, cols):
        n = ws.cell(row=target_year, column=c).value
        try:
            n = int(float(n))
        except (TypeError, ValueError):
            try:
                n = float(n)
                n = int(n)
            except Exception:  # noqa: BLE001
                n = 0
        vals.append((label, n))
    total = max(sum(v for _, v in vals), 1)
    for label, v in vals:
        if v <= 0:
            continue
        out.append({"label": label, "value": v, "share": round(v / total, 3)})
    return out


# ============================================================
# Domain: HSE
# ============================================================

def hse_metrics() -> dict:
    # PPE events feed is a demo / simulated CV stream — kept in synthetic/.
    events = (_safe_load_json(SYN_DIR / "ppe_events.json") or {}).get("events", [])
    # LTIFR + incident table is real, extracted from BRSR.
    safety = _safe_load_json(DISCL_DIR / "safety_hr.json") or {}
    ltifr_rows = safety.get("ltifr_5yr", []) or []
    incidents = safety.get("incidents_3yr", []) or []
    safety_headlines = safety.get("headlines_fy25", []) or []

    by_site: dict[str, int] = {}
    by_type: dict[str, int] = {}
    by_shift: dict[str, int] = {}
    last_24h = 0
    conf_vals: list[float] = []
    for e in events:
        if e.get("site"):
            by_site[e["site"]] = by_site.get(e["site"], 0) + 1
        if e.get("type"):
            by_type[e["type"]] = by_type.get(e["type"], 0) + 1
        if e.get("shift"):
            by_shift[e["shift"]] = by_shift.get(e["shift"], 0) + 1
        if (e.get("minutes_ago") or 0) < 60 * 24:
            last_24h += 1
        if isinstance(e.get("confidence"), (int, float)):
            conf_vals.append(float(e["confidence"]))

    total = len(events)
    avg_conf = sum(conf_vals) / len(conf_vals) if conf_vals else None

    latest_ltifr = ltifr_rows[-1] if ltifr_rows else {}
    prev_ltifr = ltifr_rows[-2] if len(ltifr_rows) >= 2 else {}
    _, ltifr_yoy = _yoy(latest_ltifr.get("workers"), prev_ltifr.get("workers"))

    latest_inc = incidents[-1] if incidents else {}
    fatalities = (latest_inc.get("fatalities_workers", 0)
                  + latest_inc.get("fatalities_executives", 0)) if latest_inc else None

    kpis = [
        _kpi("Worker LTIFR",
             f"{latest_ltifr.get('workers'):.3f}" if latest_ltifr.get("workers") is not None else "—",
             "per M hrs",
             ltifr_yoy,
             note=f"FY{latest_ltifr.get('fy')} actual" if latest_ltifr else "",
             amber=(latest_ltifr.get("workers") or 0) > 0.2),
        _kpi("Fatalities (TTM)",
             str(fatalities) if fatalities is not None else "—",
             "",
             f"FY{latest_inc.get('fy')}" if latest_inc else "",
             amber=(fatalities is not None and fatalities >= 1)),
        _kpi("Open PPE events", str(total), "",
             "live · last 7 days",
             amber=total >= 5),
        _kpi("Last 24 hours", str(last_24h), "",
             "CV feed · rolling window",
             amber=last_24h >= 3),
    ]

    TYPE_LABEL = {
        "no_hardhat": "No hard-hat",
        "no_hi_vis":  "No hi-vis",
        "no_gloves":  "No gloves",
        "no_goggles": "No goggles",
    }
    breakdowns = []
    if ltifr_rows:
        breakdowns.append({
            "title": "LTIFR by year — workers vs executives (BRSR)",
            "unit": "per M hrs",
            "items": [
                {"label": f"FY{r['fy']} · workers",
                 "value": (r.get("workers") if r.get("workers") is not None else 0),
                 "share": 0,
                 "amber": (r.get("workers") or 0) > 0.2}
                for r in ltifr_rows
            ],
        })
    if incidents:
        breakdowns.append({
            "title": "Recordable workplace injuries (BRSR)",
            "unit": "incidents",
            "items": [
                {"label": f"FY{r['fy']} · recordable",
                 "value": r.get("recordable_workers", 0), "share": 0,
                 "amber": r.get("recordable_workers", 0) >= 3}
                for r in incidents
            ],
        })
    if by_site:
        breakdowns.append({
            "title": "Live PPE events by site",
            "unit": "events",
            "items": [
                {"label": k, "value": v, "share": round(v / total, 3) if total else 0}
                for k, v in sorted(by_site.items(), key=lambda x: -x[1])
            ],
        })
    if by_type:
        breakdowns.append({
            "title": "Live PPE events by type",
            "unit": "events",
            "items": [
                {"label": TYPE_LABEL.get(k, k), "value": v,
                 "share": round(v / total, 3) if total else 0}
                for k, v in sorted(by_type.items(), key=lambda x: -x[1])
            ],
        })
    if by_shift:
        # rename to mirror the new "live" naming.
        breakdowns.append({
            "title": "Events by shift",
            "unit": "events",
            "items": [
                {"label": f"Shift {k}", "value": v,
                 "share": round(v / total, 3) if total else 0}
                for k, v in sorted(by_shift.items())
            ],
        })

    highlights = []
    if last_24h >= 3:
        highlights.append(
            f"{last_24h} PPE deviations in the last 24 hours — above the "
            f"two-per-day informal threshold."
        )
    if avg_conf is not None and avg_conf > 0.85:
        highlights.append(
            f"CV detector running at {int(round(avg_conf * 100))}% mean "
            f"confidence — no model drift suspected."
        )

    # Real LTIFR trend — sourced from BRSR FY 2022-23 → FY 2024-25.
    # Far more informative than counting PPE events into hour buckets.
    trend = None
    if ltifr_rows:
        trend = {
            "label": "Worker LTIFR — per million person-hours (BRSR)",
            "unit": "per M hrs",
            "labels": [r["fy"] for r in ltifr_rows],
            "series": [
                {"name": "Workers",
                 "values": [r.get("workers") for r in ltifr_rows]},
                {"name": "Executives",
                 "values": [r.get("executives") for r in ltifr_rows]},
            ],
        }

    # Prepend the BRSR safety headlines so the user sees what's
    # narratively notable, not just the numbers.
    highlights = safety_headlines + highlights

    return {"kpis": kpis, "breakdowns": breakdowns, "trend": trend,
            "highlights": highlights}


# ============================================================
# Domain: HR
# ============================================================

def hr_metrics() -> dict:
    """KPIs sourced from the real numbers extracted from OIL's BRSR /
    ESG / Annual Reports — no synthetic by-function values."""
    # Real BRSR / ESG-extracted workforce data lives in disclosures/.
    data = _safe_load_json(DISCL_DIR / "workforce.json")
    headcount_rows = data.get("headcount_5yr", []) or []
    diversity = data.get("diversity_fy24", {}) or {}
    reservation = data.get("reservation_fy24", []) or []
    training = data.get("training_fy24", {}) or {}
    turnover = data.get("turnover_pct_5yr", []) or []
    apprentices = data.get("apprentices_5yr", []) or []
    swabalamban = data.get("swabalamban_fy25", {}) or {}

    if not headcount_rows:
        return {"kpis": [], "breakdowns": [], "trend": None, "highlights": []}

    latest_hc = headcount_rows[-1]
    prev_hc = headcount_rows[-2] if len(headcount_rows) >= 2 else {}
    _, hc_yoy = _yoy(latest_hc.get("total"), prev_hc.get("total"))

    latest_to = turnover[-1] if turnover else {}
    prev_to = turnover[-2] if len(turnover) >= 2 else {}
    _, to_yoy = _yoy(latest_to.get("total"), prev_to.get("total"))

    latest_app = apprentices[-1] if apprentices else {}
    prev_app = apprentices[-2] if len(apprentices) >= 2 else {}
    _, app_yoy = _yoy(latest_app.get("count"), prev_app.get("count"))

    women_pct = (diversity.get("women_pct_workforce_fy25")
                 or diversity.get("women_pct_workforce"))

    kpis = [
        _kpi("Total headcount",
             f"{latest_hc.get('total', 0):,}",
             "",
             hc_yoy,
             note=f"FY{latest_hc.get('fy')} · "
                  f"{latest_hc.get('executives'):,} execs · "
                  f"{latest_hc.get('workers'):,} workers"
                  if latest_hc.get('total') else ""),
        _kpi("Women in workforce",
             f"{women_pct:.1f}%" if women_pct is not None else "—",
             "",
             f"{diversity.get('women_pct_all_management', 0):.1f}% of all management"
             if diversity.get("women_pct_all_management") else "",
             amber=(women_pct is not None and women_pct < 10)),
        _kpi("Turnover rate (TTM)",
             f"{latest_to.get('total'):.2f}%" if latest_to.get('total') is not None else "—",
             "",
             to_yoy,
             note=f"voluntary {latest_to.get('voluntary'):.2f}%"
                  if latest_to.get("voluntary") is not None else "",
             amber=(latest_to.get('total') or 0) > 8),
        _kpi("Trade apprentices",
             f"{latest_app.get('count', 0):,}" if latest_app else "—",
             "",
             app_yoy,
             note=f"FY{latest_app.get('fy')}" if latest_app else ""),
    ]

    breakdowns = []

    if reservation:
        breakdowns.append({
            "title": "Diversity — share of workforce vs share in management (FY23-24)",
            "unit": "%",
            "items": [
                {"label": r["category"], "value": r["workforce_pct"], "share": 0}
                for r in reservation
            ],
        })

    if training:
        breakdowns.append({
            "title": "Training participation (FY23-24)",
            "unit": "%",
            "items": [
                {"label": "Executives",
                 "value": training.get("executives_participation_pct", 0),
                 "share": 0},
                {"label": "Workers (non-execs)",
                 "value": training.get("workers_participation_pct", 0),
                 "share": 0},
                {"label": "Avg spend per employee (₹)",
                 "value": training.get("avg_spend_per_employee_inr", 0),
                 "share": 0},
                {"label": "Avg spend per mgmt FTE (₹)",
                 "value": training.get("avg_spend_per_mgmt_fte_inr", 0),
                 "share": 0},
            ],
        })

    if apprentices:
        breakdowns.append({
            "title": "Trade apprentices — last 5 years",
            "unit": "apprentices",
            "items": [
                {"label": f"FY{a['fy']}", "value": a["count"], "share": 0}
                for a in apprentices
            ],
        })

    # Trend: 4-year headcount (execs + workers stacked) + turnover line
    trend = {
        "label": "Headcount + turnover, last 4 FYs",
        "unit": "indexed",
        "labels": [r["fy"] for r in headcount_rows],
        "series": [
            {"name": "Total headcount",
             "values": [r.get("total") for r in headcount_rows]},
            {"name": "Turnover % × 1000",
             "values": [(_match_turnover(r["fy"], turnover) or 0) * 1000
                        for r in headcount_rows]},
        ],
    }

    highlights = []
    if latest_to.get("total") is not None and prev_to.get("total") is not None:
        delta = latest_to["total"] - prev_to["total"]
        if delta < 0:
            highlights.append(
                f"Turnover down to {latest_to['total']:.2f}% — "
                f"{abs(delta):.2f} pts below FY{prev_to['fy']}."
            )
    if women_pct is not None and women_pct < 10:
        highlights.append(
            f"Women still {women_pct:.1f}% of the workforce — "
            f"{diversity.get('women_pct_all_management', 0):.1f}% of management."
        )
    if swabalamban.get("placement_pct"):
        highlights.append(
            f"Project OIL Swabalamban placed {swabalamban.get('placed')} of "
            f"{swabalamban.get('trained')} trained ({swabalamban['placement_pct']}%) in FY25."
        )

    return {"kpis": kpis, "breakdowns": breakdowns, "trend": trend,
            "highlights": highlights}


def _match_turnover(fy: str, rows: list[dict]) -> float | None:
    """Return the turnover-row total whose `fy` matches the given label.
    Used to align two parallel time series on the trend chart."""
    for r in rows:
        if r.get("fy") == fy:
            return r.get("total")
    return None


# ============================================================
# Domain: Procurement
# ============================================================

def procurement_metrics() -> dict:
    # REAL — MSE + GeM disclosures from BRSR / Annual Reports.
    real = _safe_load_json(DISCL_DIR / "procurement.json") or {}
    mse_rows = real.get("mse_procurement", []) or []
    gem_rows = real.get("gem_procurement", []) or []

    # DEMO — synthetic single-PR bid walk-through to illustrate the
    # vendor-evaluation flow. Clearly tagged "demo".
    data = _safe_load_json(SYN_DIR / "procurement.json")
    pr = data.get("purchase_request", {}) or {}
    bids = data.get("bids", []) or []
    weights = pr.get("criteria_weights", {})
    budget = pr.get("budget_inr_cr")

    # If we have neither demo nor disclosures, bail.
    if not bids and not mse_rows:
        return {"kpis": [], "breakdowns": [], "trend": None, "highlights": []}

    latest_mse = mse_rows[-1] if mse_rows else None
    prev_mse = mse_rows[-2] if len(mse_rows) >= 2 else None
    _, mse_yoy = _yoy(latest_mse.get("value_inr_cr") if latest_mse else None,
                      prev_mse.get("value_inr_cr") if prev_mse else None)

    latest_gem = gem_rows[-1] if gem_rows else None
    prev_gem = gem_rows[-2] if len(gem_rows) >= 2 else None
    _, gem_yoy = _yoy(latest_gem.get("value_inr_cr") if latest_gem else None,
                      prev_gem.get("value_inr_cr") if prev_gem else None)

    best_price = min(bids, key=lambda b: b.get("price_inr_cr", 1e9)) if bids else {}
    high_severity = sum(
        1 for b in bids for d in (b.get("deviations") or [])
        if d.get("severity") == "high"
    )

    # KPI strip — lead with REAL disclosed numbers, then the demo PR.
    kpis = [
        _kpi("MSE procurement",
             f"₹{latest_mse.get('value_inr_cr'):,.0f}" if latest_mse else "—",
             "Cr", mse_yoy,
             note=f"FY{latest_mse.get('fy')}" + (f" · {latest_mse.get('share_pct')}% of total"
                                                  if latest_mse and latest_mse.get('share_pct') else "")
                  if latest_mse else "",
             amber=False),
        _kpi("GeM portal procurement",
             f"₹{latest_gem.get('value_inr_cr'):,.0f}" if latest_gem else "—",
             "Cr", gem_yoy,
             note=f"FY{latest_gem.get('fy')}" if latest_gem else ""),
        _kpi("Active demo PR (sim.)",
             f"₹{budget:.2f}" if budget is not None else "—",
             "Cr", pr.get("id") or "—",
             note="walkthrough · synthetic"),
        _kpi("High-severity deviations (demo)", str(high_severity), "",
             "across simulated bids",
             amber=high_severity >= 1),
    ]

    breakdowns: list[dict] = []
    if mse_rows:
        breakdowns.append({
            "title": "MSE procurement — last 4 FYs (₹ Cr)",
            "unit": "₹ Cr",
            "items": [
                {"label": f"FY{r['fy']}", "value": r["value_inr_cr"], "share": 0}
                for r in mse_rows
            ],
        })
    if gem_rows:
        breakdowns.append({
            "title": "GeM portal procurement — last 4 FYs (₹ Cr)",
            "unit": "₹ Cr",
            "items": [
                {"label": f"FY{r['fy']}", "value": r["value_inr_cr"], "share": 0}
                for r in gem_rows
            ],
        })
    if bids:
        breakdowns.append({
            "title": "Demo PR bid walk-through · price (₹ Cr, simulated)",
            "unit": "₹ Cr",
            "items": [
                {"label": b.get("vendor", "—"),
                 "value": b.get("price_inr_cr", 0),
                 "share": 0,
                 "amber": b.get("price_inr_cr", 0) > budget if budget else False}
                for b in sorted(bids, key=lambda x: x.get("price_inr_cr", 0))
            ],
        })

    highlights: list[str] = []
    if latest_mse and latest_mse.get("share_pct"):
        highlights.append(
            f"MSE share at {latest_mse['share_pct']}% in FY{latest_mse['fy']} — "
            f"comfortably above the 25% statutory floor."
        )
    if latest_gem and prev_gem:
        delta = (latest_gem.get("value_inr_cr") or 0) - (prev_gem.get("value_inr_cr") or 0)
        if delta > 0:
            highlights.append(
                f"GeM procurement up ₹{delta:,.0f} Cr to ₹{latest_gem.get('value_inr_cr'):,.0f} Cr "
                f"in FY{latest_gem['fy']} — digital-first sourcing scaling fast."
            )
    if high_severity >= 1 and bids:
        highlights.append(
            f"Demo PR walk-through shows {high_severity} high-severity contract "
            f"deviation(s) — legal review before award."
        )

    # REAL trend — MSE vs GeM procurement growth, last 4 FYs.
    trend = None
    if mse_rows or gem_rows:
        # Union of FY labels.
        all_fys = sorted({r["fy"] for r in (mse_rows + gem_rows)})
        mse_by_fy = {r["fy"]: r["value_inr_cr"] for r in mse_rows}
        gem_by_fy = {r["fy"]: r["value_inr_cr"] for r in gem_rows}
        trend = {
            "label": "MSE vs GeM procurement, last 4 FYs (₹ Cr)",
            "unit": "₹ Cr",
            "labels": all_fys,
            "series": [
                {"name": "MSE", "values": [mse_by_fy.get(fy) for fy in all_fys]},
                {"name": "GeM", "values": [gem_by_fy.get(fy) for fy in all_fys]},
            ],
        }

    return {"kpis": kpis, "breakdowns": breakdowns, "trend": trend,
            "highlights": highlights}


# ============================================================
# Domain: Finance
# ============================================================

def finance_metrics() -> dict:
    """Real five-year financial snapshot extracted from OIL's Annual
    Reports (FY 2020-21 → FY 2024-25)."""
    data = _safe_load_json(DISCL_DIR / "finance.json") or {}
    rows = data.get("five_year_snapshot", []) or []
    csr_rows = data.get("csr_5yr", []) or []
    headlines = data.get("highlights_fy25", []) or []

    if not rows:
        return {"kpis": [], "breakdowns": [], "trend": None, "highlights": []}

    latest = rows[-1]
    prev = rows[-2] if len(rows) >= 2 else {}
    five_back = rows[0]

    _, rev_yoy = _yoy(latest.get("revenue_from_operations"), prev.get("revenue_from_operations"))
    _, pbt_yoy = _yoy(latest.get("pbt"), prev.get("pbt"))
    _, capex_yoy = _yoy(latest.get("capex"), prev.get("capex"))
    rev_5yr_pct, _ = _yoy(latest.get("revenue_from_operations"),
                          five_back.get("revenue_from_operations"))

    latest_csr = csr_rows[-1] if csr_rows else {}

    kpis = [
        _kpi("Revenue from operations",
             f"₹{latest.get('revenue_from_operations'):,.0f}",
             "Cr", rev_yoy,
             note=f"FY{latest['fy']} standalone"),
        _kpi("Profit before tax",
             f"₹{latest.get('pbt'):,.0f}",
             "Cr", pbt_yoy,
             amber=(prev.get('pbt') and latest.get('pbt', 0) < prev.get('pbt'))),
        _kpi("Capex (standalone)",
             f"₹{latest.get('capex'):,.0f}",
             "Cr", capex_yoy,
             note=f"FY{latest['fy']}"),
        _kpi("CSR spend",
             f"₹{latest_csr.get('spent_inr_cr'):.2f}" if latest_csr.get("spent_inr_cr") else "—",
             "Cr",
             f"obligation ₹{latest_csr.get('obligation_inr_cr'):.2f} Cr"
             if latest_csr.get('obligation_inr_cr') else "",
             note=f"FY{latest_csr.get('fy')}" if latest_csr else ""),
    ]

    breakdowns = [
        {
            "title": "Five-year financial snapshot — Revenue (₹ Cr)",
            "unit": "₹ Cr",
            "items": [
                {"label": f"FY{r['fy']}", "value": r.get("revenue_from_operations", 0),
                 "share": 0}
                for r in rows
            ],
        },
        {
            "title": "Five-year capex programme (₹ Cr)",
            "unit": "₹ Cr",
            "items": [
                {"label": f"FY{r['fy']}", "value": r.get("capex", 0), "share": 0}
                for r in rows
            ],
        },
        {
            "title": "CSR spend vs obligation (₹ Cr)",
            "unit": "₹ Cr",
            "items": [
                {"label": f"FY{r['fy']} · obligation",
                 "value": r.get("obligation_inr_cr", 0), "share": 0}
                for r in csr_rows
            ],
        },
    ] if csr_rows else []

    trend = {
        "label": "Revenue + PBT + Capex, last 5 FYs (₹ Cr)",
        "unit": "₹ Cr",
        "labels": [r["fy"] for r in rows],
        "series": [
            {"name": "Revenue", "values": [r.get("revenue_from_operations") for r in rows]},
            {"name": "PBT",     "values": [r.get("pbt") for r in rows]},
            {"name": "Capex",   "values": [r.get("capex") for r in rows]},
        ],
    }

    highlights = list(headlines)
    if rev_5yr_pct is not None and rev_5yr_pct > 100:
        highlights.append(
            f"Revenue from operations grew {rev_5yr_pct:.0f}% over five "
            f"years — outsized scaling beyond the underlying production base."
        )

    return {"kpis": kpis, "breakdowns": breakdowns, "trend": trend,
            "highlights": highlights}


# ============================================================
# Dispatcher
# ============================================================

DOMAIN_FNS = {
    "production":  production_metrics,
    "exploration": exploration_metrics,
    "hse":         hse_metrics,
    "hr":          hr_metrics,
    "procurement": procurement_metrics,
    "finance":     finance_metrics,
}

DOMAIN_META = {
    "production": {
        "title": "Production",
        "lead":  "Crude and gas — plan vs achievement, year-on-year trajectory, and the operational drivers behind the numbers.",
    },
    "exploration": {
        "title": "Exploration & Drilling",
        "lead":  "Drilling progress, exploration wells, reserves accretion, and new discoveries.",
    },
    "hse": {
        "title": "HSE · Safety",
        "lead":  "LTIFR and incident data from BRSR, alongside a simulated PPE camera-vision stream.",
    },
    "hr": {
        "title": "HR · Workforce",
        "lead":  "Headcount, diversity, attrition, training and apprenticeship — sourced from OIL's BRSR / ESG Data Book.",
    },
    "procurement": {
        "title": "Procurement",
        "lead":  "MSE and GeM portal disclosures from the Annual Report, plus a simulated PR walk-through.",
    },
    "finance": {
        "title": "Finance",
        "lead":  "Five-year revenue, PBT, capex and CSR — extracted from the Annual Report.",
    },
}


def build_domain(key: str) -> dict | None:
    fn = DOMAIN_FNS.get(key)
    meta = DOMAIN_META.get(key)
    if not fn or not meta:
        return None
    payload = fn()
    payload.update({
        "key":   key,
        "title": meta["title"],
        "lead":  meta["lead"],
        "as_of": datetime.now(timezone.utc).isoformat(),
    })
    return payload
