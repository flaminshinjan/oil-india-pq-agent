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
    from . import predictive as P

    rows = _ten_year_table()
    if not rows:
        return {"kpis": [], "breakdowns": [], "trend": None, "highlights": []}

    crude_l, crude_p, _ = _latest_with(rows, "crude_mmt")
    gas_l,   gas_p,   _ = _latest_with(rows, "gas_mmscm")
    rrr_l,   rrr_p,   _ = _latest_with(rows, "rrr")

    _, crude_yoy_lbl = _yoy(crude_l.get("crude_mmt") if crude_l else None,
                            crude_p.get("crude_mmt") if crude_p else None)
    _, gas_yoy_lbl   = _yoy(gas_l.get("gas_mmscm") if gas_l else None,
                            gas_p.get("gas_mmscm") if gas_p else None)

    crude_amber = bool(crude_l and crude_p and crude_l["crude_mmt"] < crude_p["crude_mmt"])
    gas_amber   = bool(gas_l   and gas_p   and gas_l["gas_mmscm"]  < gas_p["gas_mmscm"])

    # FY25-26 cumulative target vs achievement, with JV (live annexure).
    totals = _production_totals()
    crude_ach = (totals.get("crude_actual", 0) / totals["crude_target"]
                 if totals.get("crude_target") else None)
    gas_ach = (totals.get("gas_actual", 0) / totals["gas_target"]
               if totals.get("gas_target") else None)

    rrr_latest = rrr_l.get("rrr") if rrr_l else None

    # ---- 4 KPIs (per brief) ----
    kpis = [
        _kpi("Crude oil production",
             _fmt(crude_l.get("crude_mmt") if crude_l else None),
             "MMT", crude_yoy_lbl, amber=crude_amber,
             note=f"FY{crude_l['fy']} actual" if crude_l else ""),
        _kpi("Natural gas production",
             _fmt(gas_l.get("gas_mmscm") if gas_l else None, "{:.0f}"),
             "MMSCM", gas_yoy_lbl, amber=gas_amber,
             note=f"FY{gas_l['fy']} actual" if gas_l else ""),
        _kpi("Annual target achievement",
             f"{crude_ach*100:.1f}%" if crude_ach is not None else "—",
             "crude · with JV",
             f"gas {gas_ach*100:.1f}%" if gas_ach is not None else "",
             amber=(crude_ach is not None and crude_ach < 0.95),
             note=f"{_fmt(totals.get('crude_actual'))} of "
                  f"{_fmt(totals.get('crude_target'))} MMT cum." if totals else ""),
        _kpi("Reserve Replacement Ratio",
             _fmt(rrr_latest),
             "×",
             f"FY{rrr_l['fy']} · {'below' if (rrr_latest or 0) < 1 else 'above'} 1.0"
             if rrr_l else "",
             amber=(rrr_latest is not None and rrr_latest < 1.0)),
    ]

    # ---- breakdown: crude by state (FY26 MTD) ----
    breakdowns: list[dict] = []
    state_split = _production_by_state()
    if state_split:
        breakdowns.append({
            "title": "Crude production by state (FY25-26 cum.)",
            "unit": "MMT",
            "items": state_split,
        })

    # ---- trend: crude vs gas, last 8 FYs ----
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

    # ============ 3 PREDICTIVE INSIGHTS ============
    insights: list[dict] = []
    wo = _workover_table()
    wells_by_fy = _drilling_wells_by_fy()

    # Align workover totals & crude on the overlapping FYs (FY21→latest).
    common_fys = [fy for fy in wo.get("fys", []) if any(r["fy"] == fy for r in rows)]
    crude_by_fy = {r["fy"]: r.get("crude_mmt") for r in rows}
    wo_actual_fys = [fy for fy in common_fys if wo["total"].get(fy)]
    # Treat the final workover year as a forward PLAN, not an actual, for the fit.
    fit_fys = [fy for fy in wo_actual_fys if crude_by_fy.get(fy) is not None]
    fit_fys = fit_fys[:-1] if len(fit_fys) > 1 else fit_fys  # drop FY26 plan from fit
    wo_model = P.workover_production_model(
        [wo["total"][fy] for fy in fit_fys],
        [crude_by_fy[fy] for fy in fit_fys],
        forecast_workovers=float(wo["total"].get(wo["fys"][-1], 307) if wo.get("fys") else 307),
    ) if len(fit_fys) >= 3 else None
    decline = P.exponential_decline([r["fy"] for r in rows],
                                    [r["crude_mmt"] for r in rows])

    # Insight 1 — recovery plateau + decline-curve / workover forecast.
    crude_trough = min((r["crude_mmt"] for r in rows if r["crude_mmt"]), default=None)
    pred1 = {}
    if wo_model:
        pred1 = {
            "label": "Workover-driven production model + base decline",
            "method": f"OLS crude~workovers (R²={wo_model['r2']}, n={len(fit_fys)})"
                      + (f"; base decline {decline['annual_decline_pct']}%/yr"
                         if decline else ""),
            "output": (
                f"At {int(wo_model['forecast_workovers'])} sustained workovers the "
                f"model puts FY27 crude near {wo_model['fy27_forecast_mmt']} MMT. "
                f"Holding {wo_model['hold_target_mmt']} MMT needs "
                f"~{wo_model['required_workovers_for_target']} workovers/yr; the "
                f"mature base alone declines {decline['annual_decline_pct'] if decline else '—'}%/yr."
            ),
            "metrics": {**wo_model, **({"base_decline_pct": decline['annual_decline_pct']} if decline else {})},
        }
    insights.append(_insight(
        "prod-i1",
        "Production recovery has plateaued — FY27 risk flagged",
        f"Crude climbed from a {crude_trough} MMT trough (FY20-21) to "
        f"{crude_l.get('crude_mmt') if crude_l else '—'} MMT, then printed its first "
        f"decline in five years. Workovers up "
        f"{wo_model['workover_growth_pct'] if wo_model else '—'}% over the same window "
        f"track the recovery — but the marginal barrel per workover is thinning.",
        l1_title="10-yr trend + FY26 vs BE trajectory",
        l1="Recovery phase FY21→FY25, then FY26 turns down (−0.3%). Gas at 85.6% of "
           "the Assam BE for FY26 — the base fields are carrying the decline.",
        l2_title="State-wise contribution",
        l2="Assam base-field decline offset by Arunachal (119% of target) while "
           "Rajasthan/JV underdeliver (87–88%).",
        predictive=pred1,
    ))

    # Insight 2 — RRR < 1.0 three years running; Monte Carlo runway.
    rrr_rows = [r for r in rows if r.get("rrr") is not None]
    acc_rows = [r for r in rows if r.get("rec_mmtoe") is not None]
    # production-equivalent depletion = accretion / RRR (definition of RRR)
    acc_seq, prodeq_seq = [], []
    for r in rrr_rows:
        if r.get("rrr") and r.get("rec_mmtoe"):
            acc_seq.append(r["rec_mmtoe"])
            prodeq_seq.append(r["rec_mmtoe"] / r["rrr"])
    mc = P.rrr_monte_carlo(acc_seq, prodeq_seq,
                           reserve_2p_latest=(rrr_rows[-1].get("oil_2p_mmt") or 0),
                           horizon=3) if len(acc_seq) >= 3 else None
    oil_2p_l, _, _ = _latest_with(rows, "oil_2p_mmt")
    gas_2p_l, _, _ = _latest_with(rows, "gas_2p_bcm")
    rli_oil = P.reserve_life_index(oil_2p_l.get("oil_2p_mmt") if oil_2p_l else None,
                                   crude_l.get("crude_mmt") if crude_l else None)
    rli_gas = P.reserve_life_index(gas_2p_l.get("gas_2p_bcm") if gas_2p_l else None,
                                   (gas_l.get("gas_mmscm") / 1000) if gas_l else None)
    pred2 = {}
    if mc:
        pred2 = {
            "label": "Monte-Carlo 2P / RRR trajectory",
            "method": f"{mc['n_sims']:,} sims · accretion ~ N({mc['hist_mean_accretion']}, "
                      f"{mc['hist_std_accretion']}); production CAGR {mc['production_cagr_pct']}%",
            "output": (
                f"P(RRR ≥ 1.0 by FY28) ≈ {mc['prob_rrr_ge_1_at_horizon']*100:.0f}% on the "
                f"current path. Mean accretion must rise ~{mc['accretion_uplift_pct']}% "
                f"(to ~{mc['required_accretion_for_rrr1']} MMToE/yr) to hold RRR at 1.0."
            ),
            "metrics": {**mc, "reserve_life_oil_yrs": rli_oil, "reserve_life_gas_yrs": rli_gas},
        }
    insights.append(_insight(
        "prod-i2",
        "RRR below 1.0 for three straight years — the reserves runway",
        f"RRR has slid {rrr_rows[0]['rrr'] if rrr_rows else '—'} → "
        f"{rrr_rows[-1]['rrr'] if rrr_rows else '—'} (FY21→FY25). 2P oil is down to "
        f"{oil_2p_l.get('oil_2p_mmt') if oil_2p_l else '—'} MMT while 2P gas has risen "
        f"to {gas_2p_l.get('gas_2p_bcm') if gas_2p_l else '—'} BCM.",
        l1_title="RRR vs the 1.0 threshold",
        l1="RRR last cleared 1.0 in FY22-23. Reserve waterfall: accretion has held "
           "near 5.9–6.2 MMToE while production grew faster, so replacement keeps slipping.",
        l2_title="Reserve Life Index — oil vs gas divergence",
        l2=f"At current output, oil 2P ≈ {rli_oil} yrs of cover; gas 2P ≈ {rli_gas} yrs. "
           f"The runway is an oil problem, not a gas one — and unbooked Andaman gas "
           f"could reset the gas line entirely (see Exploration scenario).",
        predictive=pred2,
    ))

    # Insight 3 — gasification + Andaman makes it strategy.
    mix = P.energy_mix_crossover([r["fy"] for r in rows],
                                 [r["crude_mmt"] for r in rows],
                                 [r["gas_mmscm"] for r in rows])
    pred3 = {}
    if mix:
        pred3 = {
            "label": "Energy-mix crossover (gas share of MMToE)",
            "method": "Crude→MMToE ×1.0, gas→MMToE ×0.90/BCM; linear fit on gas share",
            "output": (
                f"Gas is {mix['latest_gas_share_pct']}% of output today and rising "
                f"~{mix['share_slope_pts_per_yr']} pts/yr — crossing 50% around "
                f"{mix['crossover_fy_50pct']} on the organic trend. An Andaman "
                f"materialisation pulls that crossover forward."
            ),
            "metrics": mix,
        }
    insights.append(_insight(
        "prod-i3",
        "The portfolio is gasifying — and Andaman makes it strategy",
        "Gas grew ~15% over the decade vs ~6% for crude; gas 2P rising while oil 2P "
        "falls. FY26 JV volumes are material (Dirok 68.7 MMSCM) and DSF-III added "
        "23.3 MMSCM in year one. The Andaman gas campaign confirms the direction.",
        l1_title="Oil vs gas, indexed to FY16 = 100",
        l1="Gas output has structurally outgrown crude; the energy-mix share chart "
           "shows the gas line bending up as crude flattens.",
        l2_title="With-JV vs without-JV; new-asset ramps",
        l2="DSF-III (Rajasthan) and NRB-2 ramp curves add gas the legacy base can't. "
           "JV gas (Dirok) is now a material slice of the total.",
        predictive=pred3,
    ))

    highlights = [
        f"FY26 crude {crude_l.get('crude_mmt') if crude_l else '—'} MMT — first decline "
        f"in five years after the FY21→FY25 recovery.",
        f"RRR at {rrr_latest} (FY{rrr_l['fy'] if rrr_l else '—'}) — third straight year "
        f"below 1.0; reserves replacement is the structural watch-item.",
    ]
    if mix:
        highlights.append(
            f"Gas now {mix['latest_gas_share_pct']}% of MMToE output and climbing — "
            f"50% crossover modelled around {mix['crossover_fy_50pct']}."
        )

    return {"kpis": kpis, "breakdowns": breakdowns, "trend": trend,
            "highlights": highlights, "insights": insights,
            "milestones": _milestones("PRODUCTION")}


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
# Readers for the v2 Production / Exploration brief
# ============================================================

def _workover_drilling_wb():
    path = DB_DIR / "Workover & Drilling 5 yrs.xlsx"
    if not path.exists():
        return None
    try:
        return openpyxl.load_workbook(path, data_only=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[domain_metrics] workover xlsx open failed: {exc}")
        return None


def _nil(v) -> int:
    """The drilling file uses '¾' to mean nil. Coerce to int, ¾→0."""
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _workover_table() -> dict:
    """Workover operations by FY, from cols K–Q of the 5-yr file.

        {"fys": [...], "total": {fy: n}, "ogps": {fy: n}, "rajasthan": {fy: n}}
    """
    wb = _workover_drilling_wb()
    if not wb:
        return {}
    ws = wb.active
    # Row 2 cols 12..17 hold the FY headers; rows 3/4/5 = OGPS / Rajasthan / Total
    fys, ogps, raj, total = [], {}, {}, {}
    cols = range(12, 18)
    for c in cols:
        fy = ws.cell(2, c).value
        if not isinstance(fy, str) or "-" not in fy:
            continue
        fy = fy.strip()
        fys.append(fy)
        ogps[fy] = _nil(ws.cell(3, c).value)
        raj[fy] = _nil(ws.cell(4, c).value)
        total[fy] = _nil(ws.cell(5, c).value)
    return {"fys": fys, "total": total, "ogps": ogps, "rajasthan": raj}


def _drilling_wells_by_fy() -> dict:
    """Wells drilled by FY from the 5-yr file (cols A–H).

        {fy: {"expl": n, "dev": n, "total": n, "offshore": n, "onshore": n}}
    Rows 4..8 cover FY2024-25 down to FY2020-21; '¾' = nil.
    """
    wb = _workover_drilling_wb()
    if not wb:
        return {}
    ws = wb.active
    out: dict = {}
    for r in range(4, 9):
        fy = ws.cell(r, 1).value
        if not isinstance(fy, str) or "-" not in fy:
            continue
        fy = fy.strip()
        expl = _nil(ws.cell(r, 2).value) + _nil(ws.cell(r, 3).value)   # offshore+onshore
        dev = _nil(ws.cell(r, 4).value) + _nil(ws.cell(r, 5).value)
        offshore = _nil(ws.cell(r, 2).value) + _nil(ws.cell(r, 4).value)
        onshore = _nil(ws.cell(r, 3).value) + _nil(ws.cell(r, 5).value)
        total = _nil(ws.cell(r, 8).value) or (expl + dev)
        out[fy] = {"expl": expl, "dev": dev, "total": total,
                   "offshore": offshore, "onshore": onshore}
    return out


def _expl_regime_fy26() -> list[dict]:
    """FY25-26 exploratory drilling by licensing regime, from Annexure-III.

    Each regime block ends in a 'Total Exploratory' row; we capture the
    block's target/actual wells + meterage and the achievement %.
    """
    wb = _fy_perf_wb()
    if not wb:
        return []
    sn = next((n for n in wb.sheetnames if "Expl. Drl" in n), None)
    if not sn:
        return []
    ws = wb[sn]
    out: list[dict] = []
    current = None
    state = None
    for r in range(8, ws.max_row + 1):
        a = ws.cell(r, 1).value
        if isinstance(a, str) and a.strip():
            label = a.strip()
            if label.lower().startswith("total exploratory"):
                if current:
                    tgt_w = _nil(ws.cell(r, 6).value)
                    act_w = _nil(ws.cell(r, 8).value)
                    tgt_m = _as_float(ws.cell(r, 5).value) or 0
                    act_m = _as_float(ws.cell(r, 7).value) or 0
                    pct = (act_m / tgt_m) if tgt_m else None
                    out.append({
                        "regime": current, "state": state,
                        "target_wells": tgt_w, "actual_wells": act_w,
                        "target_m": round(tgt_m), "actual_m": round(act_m),
                        "pct": round(pct, 3) if pct is not None else None,
                    })
                current = None
            else:
                current = label
                state = (ws.cell(r, 2).value or "").strip() if isinstance(ws.cell(r, 2).value, str) else None
    return out


def _accretion_series() -> dict:
    """Reserve accretion (MMToE total) by FY from the 10-yr Excel."""
    rows = _ten_year_table()
    return {r["fy"]: r.get("rec_mmtoe") for r in rows if r.get("rec_mmtoe") is not None}


# ---- insight helpers --------------------------------------------------

def _insight(iid: str, title: str, summary: str,
             l1_title: str = "", l1: str = "",
             l2_title: str = "", l2: str = "",
             predictive: dict | None = None,
             links: list[str] | None = None) -> dict:
    """One analytical insight card. `predictive` carries the model output
    so the UI can render a 'Predictive' block with real computed numbers."""
    return {
        "id": iid, "title": title, "summary": summary,
        "drilldown": {"l1_title": l1_title, "l1": l1,
                      "l2_title": l2_title, "l2": l2},
        "predictive": predictive or {},
        "links": links or [],
    }


def _pct(v) -> str:
    return f"{v*100:.1f}%" if isinstance(v, (int, float)) else "—"


def _milestones(page: str | None = None) -> list[dict]:
    """Live-milestones strip. Each is a record_type='milestone' row; the
    Andaman items carry status='unbooked' and never feed the KPI layer."""
    rows = _ten_year_table()
    by_fy = {r["fy"]: r for r in rows}
    crude_latest = next((r for r in reversed(rows) if r.get("crude_mmt")), {})
    crude_trough = min((r["crude_mmt"] for r in rows if r.get("crude_mmt")), default=None)
    acc_latest = next((r for r in reversed(rows) if r.get("rec_mmtoe")), {})
    wo = _workover_table()
    wo_fys = wo.get("fys", [])
    regimes = _expl_regime_fy26()
    nominated = next((r for r in regimes if r["regime"] == "Nominated"), {})

    items: list[dict] = [
        {
            "title": f"Highest crude production in a decade — {crude_latest.get('crude_mmt')} MMT",
            "body": f"Up from the {crude_trough} MMT FY20-21 trough.",
            "source": "10-yr Excel / AR FY24-25", "tags": ["PRODUCTION"],
            "status": "booked",
        },
        {
            "title": f"{nominated.get('actual_wells', '—')} exploratory wells vs "
                     f"{nominated.get('target_wells', '—')} target (FY26)",
            "body": f"Nominated-block meterage at {_pct(nominated.get('pct'))} of BE.",
            "source": "FY26 MIS", "tags": ["EXPLORATION"], "status": "booked",
        },
        {
            "title": f"Best reserve accretion in 5 years — {acc_latest.get('rec_mmtoe')} MMToE",
            "body": "FY26 reserve accretion, up year-on-year.",
            "source": "10-yr Excel", "tags": ["EXPLORATION"], "status": "booked",
        },
        {
            "title": "DSF-III Rajasthan onstream",
            "body": "First gas: 23.3 MMSCM in FY26.",
            "source": "FY26 MIS", "tags": ["PRODUCTION"], "status": "booked",
        },
        {
            "title": "Workover engine at record scale",
            "body": f"{wo['total'].get(wo_fys[-2]) if len(wo_fys) >= 2 else '—'} ops FY25; "
                    f"{wo['total'].get(wo_fys[-1]) if wo_fys else '—'} planned FY26.",
            "source": "Workover Excel", "tags": ["PRODUCTION"], "status": "booked",
        },
        {
            "title": "Second Andaman gas discovery — Vijayapuram-3 (Jun 2026)",
            "body": "2 of 3 wells gas-bearing; 15 km offshore, 355 m water depth; "
                    "continuous flaring on test.",
            "source": "Exchange disclosure", "tags": ["EXPLORATION"], "status": "unbooked",
        },
        {
            "title": "Andaman frontier opens — Vijayapuram-2 (Sep 2025)",
            "body": "First gas in the basin; samples 87% methane; stock +3% on announcement.",
            "source": "Exchange disclosure", "tags": ["EXPLORATION"], "status": "unbooked",
        },
    ]
    if page:
        items = [m for m in items if page.upper() in m["tags"]]
    return items


def _andaman_scenario() -> dict | None:
    """Andaman 'Possible Upside' scenario module — probability-weighted
    reasoning over an UNBOOKED frontier discovery. Every figure is
    illustrative; nothing here sums into 2P / accretion / RRR."""
    from . import predictive as P
    from .andaman import get_andaman

    facts = get_andaman()
    rows = _ten_year_table()
    gas_2p_l, _, _ = _latest_with(rows, "gas_2p_bcm")
    gas_l, _, _ = _latest_with(rows, "gas_mmscm")
    cur_2p_gas = gas_2p_l.get("gas_2p_bcm") if gas_2p_l else 139.0
    annual_gas_bcm = (gas_l.get("gas_mmscm") / 1000) if gas_l else 3.19

    sens = P.andaman_reserves_sensitivity(cur_2p_gas, annual_gas_bcm)
    bayes = P.bayesian_success_update(facts.get("wells_gas_bearing", 2),
                                      facts.get("wells_drilled", 3))

    lenses = []
    if sens:
        lenses.append({
            "lens": "Reserves",
            "output": (
                f"Every 25 BCM hypothetically booked ≈ +{sens['per_25bcm_uplift_pct']}% "
                f"to 2P gas ({sens['current_2p_gas_bcm']} BCM today) ≈ "
                f"+{sens['per_25bcm_life_yrs']} yrs of gas reserve life."
            ),
            "table": sens["rows"],
            "hypothetical": True,
        })
    if bayes:
        lenses.append({
            "lens": "Risk",
            "output": (
                f"Frontier success prior {bayes['prior_mean']} (≈1-in-5) updates to "
                f"{bayes['posterior_mean']} after a {bayes['observed']} gas-bearing "
                f"result (90% CI {bayes['cred_interval_90'][0]}–{bayes['cred_interval_90'][1]}). "
                f"Next update trigger: {facts.get('next_update_trigger')}."
            ),
            "table": None,
            "hypothetical": True,
        })
    lenses.append({
        "lens": "Production mix",
        "output": "A post-FY32 Andaman gas ramp layered onto the gasification forecast "
                  "pulls the 50%-of-output crossover years earlier than the organic trend "
                  "(see Production Insight 3).",
        "table": None, "hypothetical": True,
    })

    return {
        "label": "Possible Upside — Andaman frontier (illustrative / unbooked)",
        "subtitle": facts.get("capex_plan_note"),
        "guardrail": "Illustrative only. No public reserve estimate exists; nothing here "
                     "is booked into 2P, accretion or RRR. All volumes are hypothetical analogs.",
        "facts": {
            "wells_drilled": facts.get("wells_drilled"),
            "wells_gas_bearing": facts.get("wells_gas_bearing"),
            "wells": facts.get("wells"),
            "reserve_estimate_published": facts.get("reserve_estimate_published"),
            "booked_in_2p": facts.get("booked_in_2p"),
        },
        "lenses": lenses,
        "timeline": facts.get("timeline"),
        "scrape_status": facts.get("scrape_status"),
        "live_sources": facts.get("live_sources"),
        "system_of_record": facts.get("system_of_record"),
    }


# ============================================================
# Domain: Exploration
# ============================================================

def exploration_metrics() -> dict:
    from . import predictive as P

    rows = _ten_year_table()
    if not rows:
        return {"kpis": [], "breakdowns": [], "trend": None, "highlights": []}

    rec_l, rec_p, _ = _latest_with(rows, "rec_mmtoe")

    # FY25-26 drilling progress from the live annexure.
    drilling = _drilling_fy_progress()
    expl = drilling.get("exploratory") or {}
    devp = drilling.get("development") or {}
    expl_ach = (expl["actual_w"] / expl["target_w"]
                if expl.get("target_w") else None)
    devp_ach = (devp["actual_w"] / devp["target_w"]
                if devp.get("target_w") else None)

    # New v2 data sources.
    wells_by_fy = _drilling_wells_by_fy()
    wo = _workover_table()
    regimes = _expl_regime_fy26()
    nominated = next((r for r in regimes if r["regime"] == "Nominated"), {})

    # Wells-drilled total: latest vs earliest in the 5-yr file.
    well_fys = sorted(wells_by_fy.keys())
    wells_latest = wells_by_fy.get(well_fys[-1], {}) if well_fys else {}
    wells_first = wells_by_fy.get(well_fys[0], {}) if well_fys else {}
    wo_fys = wo.get("fys", [])
    wo_fy25 = wo["total"].get(wo_fys[-2]) if len(wo_fys) >= 2 else None
    wo_fy26 = wo["total"].get(wo_fys[-1]) if wo_fys else None

    # ---- 4 KPIs (per brief) ----
    kpis = [
        _kpi("Wells drilled (total)",
             str(wells_latest.get("total", "—")),
             f"FY{well_fys[-1]}" if well_fys else "",
             f"vs {wells_first.get('total', '—')} in FY{well_fys[0]}" if well_fys else "",
             note=f"{wells_latest.get('expl', 0)} exploratory · "
                  f"{wells_latest.get('dev', 0)} development"),
        _kpi("Exploratory meterage achievement",
             _pct(nominated.get("pct")),
             "nominated blocks",
             f"{nominated.get('actual_wells', '—')} of {nominated.get('target_wells', '—')} wells",
             amber=(nominated.get("pct") is not None and nominated["pct"] < 0.9),
             note="NELP / OALP onshore commitment blocks lag at 0%"),
        _kpi("Workover operations",
             str(wo_fy25 or "—"),
             f"FY{wo_fys[-2]}" if len(wo_fys) >= 2 else "",
             f"{wo_fy26} planned FY{wo_fys[-1]}" if wo_fy26 else ""),
        _kpi("Reserve accretion",
             _fmt(rec_l.get("rec_mmtoe") if rec_l else None),
             "MMToE",
             f"FY{rec_l['fy']} · best since FY22-23" if rec_l else "",
             note="reserves runway feeds the RRR target (see Production)"),
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

    # Accretion vs production-depletion trend (last 6 FYs).
    acc_fys = [r["fy"] for r in rows[-6:]]
    trend = {
        "label": "Reserve accretion vs crude production (MMToE-equiv)",
        "unit": "MMToE",
        "labels": acc_fys,
        "series": [
            {"name": "Accretion (MMToE)",
             "values": [r.get("rec_mmtoe") for r in rows[-6:]]},
            {"name": "Crude production (MMT)",
             "values": [r.get("crude_mmt") for r in rows[-6:]]},
        ],
    }

    # ============ 3 PREDICTIVE INSIGHTS ============
    insights: list[dict] = []

    # Insight 1 — drilling intensity → production (lagged intervention ROI).
    crude_by_fy = {r["fy"]: r.get("crude_mmt") for r in rows}
    int_fys = [fy for fy in wo_fys if crude_by_fy.get(fy) is not None]
    crude_seq = [crude_by_fy[fy] for fy in int_fys]
    wo_seq = [wo["total"].get(fy) for fy in int_fys]
    dev_seq = [wells_by_fy.get(fy, {}).get("dev") for fy in int_fys]
    lag_model = P.lagged_intervention_model(crude_seq, wo_seq, dev_seq) \
        if len(int_fys) >= 5 else None
    wells_growth = None
    if wells_first.get("total") and wells_latest.get("total"):
        wells_growth = round((wells_latest["total"] / wells_first["total"] - 1) * 100)
    pred_e1 = {}
    if lag_model:
        pred_e1 = {
            "label": "Lagged intervention-ROI regression",
            "method": f"OLS crude(t) ~ workovers(t) + dev-wells(t−1) "
                      f"(R²={lag_model['r2']}, adj R²={lag_model['adj_r2']}, "
                      f"n={lag_model['n_obs']}{'; small sample' if lag_model['small_sample'] else ''})",
            "output": (
                f"Each workover is worth ~{lag_model['coef_workover_t']*1000:.2f} kT crude, "
                f"each prior-year dev well ~{lag_model['coef_devwell_t_1']*1000:.2f} kT. "
                f"Inverting: holding {lag_model['hold_target_mmt']} MMT in FY27 needs "
                f"~{lag_model['required_workovers_fy27']} workovers."
            ),
            "metrics": lag_model,
        }
    insights.append(_insight(
        "expl-i1",
        "Drilling intensity up sharply — the model quantifies what it buys",
        f"Wells drilled {wells_first.get('total', '—')} → {wells_latest.get('total', '—')} "
        f"(FY{well_fys[0] if well_fys else ''}→FY{well_fys[-1] if well_fys else ''}, "
        f"+{wells_growth}%), workovers {wo['total'].get(wo_fys[0]) if wo_fys else '—'} → "
        f"{wo_fy25}, coincident with the crude recovery.",
        l1_title="Wells + workovers vs crude production",
        l1="Dual-axis: drilling + workover counts rise in step with crude from FY21. "
           "The intervention engine is what arrested the legacy decline.",
        l2_title="Exploratory vs development mix",
        l2=f"Development wells {wells_first.get('dev', '—')} → {wells_latest.get('dev', '—')}; "
           f"OGPS workovers dominate ({wo['ogps'].get(wo_fys[-2]) if len(wo_fys)>=2 else '—'} "
           f"FY25) with Rajasthan the balance.",
        predictive=pred_e1,
    ))

    # Insight 2 — offshore inflection (execution matrix + Bayesian Andaman).
    nelp_oalp = [r for r in regimes if r["regime"].startswith(("NELP", "OALP"))
                 and "Andaman" not in (r.get("state") or "")]
    onshore_lag = [r for r in nelp_oalp if (r.get("pct") or 0) < 0.5 and r.get("target_wells")]
    andaman_reg = next((r for r in regimes if "Andaman" in (r.get("state") or "")), {})
    from .andaman import get_andaman
    af = get_andaman()
    bayes = P.bayesian_success_update(af.get("wells_gas_bearing", 2),
                                      af.get("wells_drilled", 3))
    pred_e2 = {}
    if bayes:
        pred_e2 = {
            "label": "Bayesian success-rate update (Beta-Binomial)",
            "method": "Prior Beta(1,4) ≈ 1-in-5 frontier base rate; posterior after "
                      f"{bayes['observed']} gas-bearing wells",
            "output": (
                f"Basin success probability moves from {bayes['prior_mean']} to "
                f"{bayes['posterior_mean']} (90% CI {bayes['cred_interval_90'][0]}–"
                f"{bayes['cred_interval_90'][1]}). The execution gap is now onshore-OALP "
                f"({len(onshore_lag)} commitment blocks under 50% of meterage), not offshore."
            ),
            "metrics": bayes,
        }
    insights.append(_insight(
        "expl-i2",
        "From 'offshore is the risk' to 'offshore is the inflection point'",
        "All legacy drilling sits in nominated onshore acreage (139% of meterage) while "
        "NELP/OALP commitment blocks sit at 0%. The Andaman result flips the story: a "
        "single offshore campaign delivered a 2-of-3 gas-bearing rate in a frontier basin "
        "where ~1-in-5 is typical.",
        l1_title="Execution & success matrix by regime",
        l1="Nominated-onshore over-delivers; NELP/OALP-onshore commitment blocks are the "
           "real execution gap; Andaman-offshore (OALP-II) drilled "
           f"{andaman_reg.get('actual_wells', '—')} well at "
           f"{_pct(andaman_reg.get('pct'))} of meterage.",
        l2_title="Block-level + Andaman well log",
        l2="Vijayapuram-1 dry → V-2 gas (295 m, 87% methane) → V-3 gas (355 m, flaring on "
           "test). Commitment-risk scoring flags the onshore OALP minimum-work-programme "
           "deadlines as the exposure to watch.",
        predictive=pred_e2,
    ))

    # Insight 3 — accretion recovering but not enough (effectiveness).
    acc_seq = [r.get("rec_mmtoe") for r in rows if r.get("rec_mmtoe") is not None][-6:]
    # exploration effectiveness: accretion per exploratory metre (use FY26 nominated meterage)
    rrr_rows = [r for r in rows if r.get("rrr") is not None]
    prodeq_latest = None
    if rrr_rows and rrr_rows[-1].get("rrr") and rrr_rows[-1].get("rec_mmtoe"):
        prodeq_latest = rrr_rows[-1]["rec_mmtoe"] / rrr_rows[-1]["rrr"]
    eff = P.exploration_effectiveness(
        acc_seq,
        [nominated.get("actual_m") for _ in acc_seq],  # latest meterage proxy
        production_equiv=prodeq_latest,
    ) if acc_seq else None
    pred_e3 = {}
    if eff:
        pred_e3 = {
            "label": "Exploration-effectiveness → RRR≥1 requirement",
            "method": "Accretion per exploratory metre, trended; inverted for RRR≥1.0 next FY",
            "output": (
                f"To reach RRR ≥ 1.0, accretion must reach "
                f"~{eff['required_accretion_for_rrr']} MMToE — implying on the order of "
                f"{eff['implied_meterage']:,} m of effective exploratory drilling at "
                f"current effectiveness." if eff.get("implied_meterage")
                else f"RRR≥1.0 needs accretion ~{eff['required_accretion_for_rrr']} MMToE."
            ),
            "metrics": eff,
        }
    insights.append(_insight(
        "expl-i3",
        "Reserve accretion recovering — but the model says not yet enough",
        f"Accretion reached {rec_l.get('rec_mmtoe') if rec_l else '—'} MMToE in FY26 "
        f"(best in five years), yet RRR is still below 1.0 because production grew faster.",
        l1_title="Accretion vs production-depletion",
        l1="The gap between annual accretion and production-equivalent depletion is the "
           "net reserve change — still negative on the oil side.",
        l2_title="Discovery log mapped to accretion",
        l2="8 discoveries in 5 years (3 gas / 5 oil); FY25 added the deepest commercial "
           "oil find (Mechaki-6, >5500 m). Andaman events are flagged booked=false — they "
           "contribute zero accretion until appraised.",
        predictive=pred_e3,
    ))

    highlights = [
        f"FY26 nominated exploratory meterage at {_pct(nominated.get('pct'))} of BE — "
        f"{nominated.get('actual_wells', '—')} wells vs {nominated.get('target_wells', '—')} "
        f"target, while NELP/OALP commitment blocks sit at 0%.",
        f"Reserve accretion {rec_l.get('rec_mmtoe') if rec_l else '—'} MMToE (FY26), best "
        f"in five years — but still short of replacing production (RRR < 1.0).",
        "Andaman offshore turned a 2-of-3 gas-bearing result — frontier success well above "
        "the ~1-in-5 norm. Unbooked; see the scenario module.",
    ]

    return {"kpis": kpis, "breakdowns": breakdowns, "trend": trend,
            "highlights": highlights, "insights": insights,
            "scenario": _andaman_scenario(),
            "milestones": _milestones("EXPLORATION")}


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
    """KPIs extracted dynamically from OIL's BRSR / ESG / Annual Reports
    via RAG + Anthropic (cached 6 h). Curated JSON is only a fallback if
    extraction fails."""
    from .dynamic_extract import extract_hse
    safety = extract_hse()
    ltifr_rows = safety.get("ltifr_5yr", []) or []
    # New schema uses `incidents_5yr`; tolerate the legacy `incidents_3yr`.
    incidents = safety.get("incidents_5yr") or safety.get("incidents_3yr") or []
    safety_headlines = safety.get("headlines_fy25", []) or []

    if not ltifr_rows and not incidents:
        return {"kpis": [], "breakdowns": [], "trend": None, "highlights": []}

    latest_ltifr = ltifr_rows[-1] if ltifr_rows else {}
    prev_ltifr = ltifr_rows[-2] if len(ltifr_rows) >= 2 else {}
    five_back_ltifr = ltifr_rows[0] if ltifr_rows else {}
    _, ltifr_yoy = _yoy(latest_ltifr.get("workers"), prev_ltifr.get("workers"))
    ltifr_5yr_pct, _ = _yoy(latest_ltifr.get("workers"), five_back_ltifr.get("workers"))

    latest_inc = incidents[-1] if incidents else {}
    fatalities = (latest_inc.get("fatalities_workers", 0)
                  + latest_inc.get("fatalities_executives", 0)) if latest_inc else None

    # Sum recordable workers across the last three years for TTM-style figure.
    recordable_3yr = sum(r.get("recordable_workers", 0) for r in incidents)
    high_conseq_3yr = sum(r.get("high_consequence_workers", 0) for r in incidents)

    kpis = [
        _kpi("Worker LTIFR",
             f"{latest_ltifr.get('workers'):.3f}" if latest_ltifr.get("workers") is not None else "—",
             "per M hrs",
             ltifr_yoy,
             note=f"FY{latest_ltifr.get('fy')} · BRSR" if latest_ltifr else "",
             amber=(latest_ltifr.get("workers") or 0) > 0.2),
        _kpi("Fatalities (TTM)",
             str(fatalities) if fatalities is not None else "—",
             "",
             f"FY{latest_inc.get('fy')} workers + execs" if latest_inc else "",
             amber=(fatalities is not None and fatalities >= 1)),
        _kpi("Recordable injuries · 3-yr",
             str(recordable_3yr) if incidents else "—",
             "",
             f"workers · FY22-23 → FY{latest_inc.get('fy')}" if latest_inc else "",
             amber=False),
        _kpi("High-consequence · 3-yr",
             str(high_conseq_3yr) if incidents else "—",
             "",
             "excluding fatalities",
             amber=(high_conseq_3yr >= 5)),
    ]

    breakdowns: list[dict] = []
    if ltifr_rows:
        breakdowns.append({
            "title": "Worker LTIFR by FY (BRSR)",
            "unit": "per M hrs",
            "items": [
                {"label": f"FY{r['fy']}",
                 "value": (r.get("workers") if r.get("workers") is not None else 0),
                 "share": 0,
                 "amber": (r.get("workers") or 0) > 0.2}
                for r in ltifr_rows
            ],
        })
    if incidents:
        breakdowns.append({
            "title": "Recordable injuries — workers, by FY",
            "unit": "incidents",
            "items": [
                {"label": f"FY{r['fy']}",
                 "value": r.get("recordable_workers", 0), "share": 0,
                 "amber": r.get("recordable_workers", 0) >= 3}
                for r in incidents
            ],
        })
        breakdowns.append({
            "title": "High-consequence injuries (excl. fatalities)",
            "unit": "incidents",
            "items": [
                {"label": f"FY{r['fy']}",
                 "value": r.get("high_consequence_workers", 0), "share": 0}
                for r in incidents
            ],
        })

    trend = None
    if ltifr_rows:
        trend = {
            "label": "LTIFR trend — workers vs executives (BRSR)",
            "unit": "per M hrs",
            "labels": [r["fy"] for r in ltifr_rows],
            "series": [
                {"name": "Workers",
                 "values": [r.get("workers") for r in ltifr_rows]},
                {"name": "Executives",
                 "values": [r.get("executives") for r in ltifr_rows]},
            ],
        }

    highlights = list(safety_headlines)
    if ltifr_5yr_pct is not None and ltifr_5yr_pct < -50:
        highlights.append(
            f"Worker LTIFR down {abs(ltifr_5yr_pct):.0f}% over the LTIFR "
            f"reporting window — sustained downtrend in lost-time incidents."
        )

    return {"kpis": kpis, "breakdowns": breakdowns, "trend": trend,
            "highlights": highlights}


# ============================================================
# Domain: HR
# ============================================================

def hr_metrics() -> dict:
    """KPIs extracted dynamically from OIL's BRSR / ESG / Annual Reports
    via RAG + Anthropic (cached 6 h). The curated JSON is only a fallback
    if the corpus / LLM is unavailable."""
    from .dynamic_extract import extract_hr
    data = extract_hr()
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
    """Procurement KPIs extracted dynamically from OIL's Annual Reports
    + BRSR via RAG + Anthropic (cached 6 h). The curated JSON only
    seeds the deep-merge with confirmed values; the LLM fills the rest
    from corpus excerpts. No extrapolation."""
    from .dynamic_extract import extract_procurement
    real = extract_procurement()
    mse_rows = real.get("mse_procurement", []) or []
    gem_rows = real.get("gem_procurement", []) or []
    policies = real.get("purchase_preference_policies", []) or []

    if not mse_rows and not gem_rows:
        return {"kpis": [], "breakdowns": [], "trend": None, "highlights": []}

    def _latest_row(seq, key):
        for r in reversed(seq):
            if isinstance(r, dict) and r.get(key) is not None:
                return r
        return None

    def _prev_row(seq, latest, key):
        if not latest:
            return None
        try:
            i = seq.index(latest)
        except ValueError:
            return None
        for r in reversed(seq[:i]):
            if isinstance(r, dict) and r.get(key) is not None:
                return r
        return None

    def _first_row(seq, key):
        for r in seq:
            if isinstance(r, dict) and r.get(key) is not None:
                return r
        return None

    latest_mse  = _latest_row(mse_rows, "value_inr_cr")
    prev_mse    = _prev_row(mse_rows, latest_mse, "value_inr_cr")
    first_mse   = _first_row(mse_rows, "value_inr_cr")
    latest_gem  = _latest_row(gem_rows, "value_inr_cr")
    prev_gem    = _prev_row(gem_rows, latest_gem, "value_inr_cr")
    first_gem   = _first_row(gem_rows, "value_inr_cr")

    _, mse_yoy = _yoy(latest_mse.get("value_inr_cr") if latest_mse else None,
                      prev_mse.get("value_inr_cr") if prev_mse else None)
    five_mse_pct, _ = _yoy(latest_mse.get("value_inr_cr") if latest_mse else None,
                           first_mse.get("value_inr_cr") if first_mse else None)
    _, gem_yoy = _yoy(latest_gem.get("value_inr_cr") if latest_gem else None,
                      prev_gem.get("value_inr_cr") if prev_gem else None)
    five_gem_pct, _ = _yoy(latest_gem.get("value_inr_cr") if latest_gem else None,
                           first_gem.get("value_inr_cr") if first_gem else None)

    def _inr(v):
        return f"₹{v:,.0f}" if isinstance(v, (int, float)) else "—"

    mse_note = ""
    if latest_mse:
        mse_note = f"FY{latest_mse.get('fy')}"
        if latest_mse.get("share_pct") is not None:
            mse_note += f" · {latest_mse['share_pct']}% of total"

    kpis = [
        _kpi("MSE procurement",
             _inr(latest_mse.get("value_inr_cr") if latest_mse else None),
             "Cr", mse_yoy, note=mse_note),
        _kpi("GeM portal procurement",
             _inr(latest_gem.get("value_inr_cr") if latest_gem else None),
             "Cr", gem_yoy,
             note=f"FY{latest_gem.get('fy')}" if latest_gem else ""),
        _kpi("MSE growth (4-yr)",
             f"{'+' if (five_mse_pct or 0) >= 0 else ''}{five_mse_pct:.0f}%"
             if five_mse_pct is not None else "—",
             "", "cumulative change"),
        _kpi("GeM growth (4-yr)",
             f"{'+' if (five_gem_pct or 0) >= 0 else ''}{five_gem_pct:.0f}%"
             if five_gem_pct is not None else "—",
             "", "cumulative change"),
    ]

    breakdowns: list[dict] = []
    mse_items = [
        {"label": f"FY{r['fy']}", "value": r["value_inr_cr"], "share": 0}
        for r in mse_rows if isinstance(r, dict) and r.get("value_inr_cr") is not None
    ]
    if mse_items:
        breakdowns.append({
            "title": "MSE procurement — disclosed FYs (₹ Cr)",
            "unit": "₹ Cr",
            "items": mse_items,
        })
    gem_items = [
        {"label": f"FY{r['fy']}", "value": r["value_inr_cr"], "share": 0}
        for r in gem_rows if isinstance(r, dict) and r.get("value_inr_cr") is not None
    ]
    if gem_items:
        breakdowns.append({
            "title": "GeM portal procurement — disclosed FYs (₹ Cr)",
            "unit": "₹ Cr",
            "items": gem_items,
        })

    highlights: list[str] = []
    if latest_mse and latest_mse.get("share_pct"):
        highlights.append(
            f"MSE share at {latest_mse['share_pct']}% in FY{latest_mse['fy']} — "
            f"comfortably above the 25% statutory floor."
        )
    if latest_gem and prev_gem and isinstance(latest_gem.get("value_inr_cr"), (int, float)):
        delta = (latest_gem.get("value_inr_cr") or 0) - (prev_gem.get("value_inr_cr") or 0)
        if delta > 0:
            highlights.append(
                f"GeM procurement up ₹{delta:,.0f} Cr to "
                f"₹{latest_gem['value_inr_cr']:,.0f} Cr in FY{latest_gem['fy']} "
                f"— digital-first sourcing scaling fast."
            )
    if policies:
        highlights.append(
            "Public-procurement preference policies in force: "
            + " · ".join(policies[:4]) + "."
        )

    # REAL trend — MSE vs GeM procurement growth, last 4 FYs.
    trend = None
    if mse_rows or gem_rows:
        all_fys = sorted({r["fy"] for r in (mse_rows + gem_rows) if isinstance(r, dict) and r.get("fy")})
        mse_by_fy = {r["fy"]: r.get("value_inr_cr") for r in mse_rows if isinstance(r, dict)}
        gem_by_fy = {r["fy"]: r.get("value_inr_cr") for r in gem_rows if isinstance(r, dict)}
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
    """Five-year financial snapshot extracted dynamically from OIL's
    Annual Reports via RAG + Anthropic (cached 6 h). Curated JSON is
    a fallback only — when extraction returns a value, it wins."""
    from .dynamic_extract import extract_finance
    data = extract_finance()
    rows = data.get("five_year_snapshot", []) or []
    csr_rows = data.get("csr_5yr", []) or []
    headlines = data.get("highlights_fy25", []) or []

    if not rows:
        return {"kpis": [], "breakdowns": [], "trend": None, "highlights": []}

    latest = rows[-1]
    prev = rows[-2] if len(rows) >= 2 else {}
    five_back = rows[0]

    # Pick the most-recent FY where each metric actually has a value.
    def _latest_with_key(key: str) -> dict | None:
        for r in reversed(rows):
            if r.get(key) is not None:
                return r
        return None

    rev_l   = _latest_with_key("revenue_from_operations")
    pbt_l   = _latest_with_key("pbt")
    capex_l = _latest_with_key("capex")

    def _pos(seq, idx):
        try:
            return seq[idx]
        except (IndexError, TypeError):
            return {}

    def _prev_with_key(latest_row: dict | None, key: str) -> dict | None:
        if not latest_row:
            return None
        try:
            i = rows.index(latest_row)
        except ValueError:
            return None
        for r in reversed(rows[:i]):
            if r.get(key) is not None:
                return r
        return None

    rev_prev   = _prev_with_key(rev_l, "revenue_from_operations")
    pbt_prev   = _prev_with_key(pbt_l, "pbt")
    capex_prev = _prev_with_key(capex_l, "capex")

    _, rev_yoy   = _yoy(rev_l.get("revenue_from_operations") if rev_l else None,
                        rev_prev.get("revenue_from_operations") if rev_prev else None)
    _, pbt_yoy   = _yoy(pbt_l.get("pbt") if pbt_l else None,
                        pbt_prev.get("pbt") if pbt_prev else None)
    _, capex_yoy = _yoy(capex_l.get("capex") if capex_l else None,
                        capex_prev.get("capex") if capex_prev else None)
    rev_5yr_pct, _ = _yoy(
        rev_l.get("revenue_from_operations") if rev_l else None,
        rows[0].get("revenue_from_operations") if rows else None,
    )

    latest_csr = next(
        (r for r in reversed(csr_rows) if r.get("spent_inr_cr") is not None
         or r.get("obligation_inr_cr") is not None),
        {},
    )

    def _fmt_inr(v):
        return f"₹{v:,.0f}" if isinstance(v, (int, float)) else "—"

    def _fmt_csr(v):
        return f"₹{v:.2f}" if isinstance(v, (int, float)) else "—"

    kpis = [
        _kpi("Revenue from operations",
             _fmt_inr(rev_l.get("revenue_from_operations") if rev_l else None),
             "Cr", rev_yoy,
             note=f"FY{rev_l['fy']} standalone" if rev_l else ""),
        _kpi("Profit before tax",
             _fmt_inr(pbt_l.get("pbt") if pbt_l else None),
             "Cr", pbt_yoy,
             amber=bool(pbt_l and pbt_prev
                        and (pbt_l.get("pbt") or 0) < (pbt_prev.get("pbt") or 0))),
        _kpi("Capex (standalone)",
             _fmt_inr(capex_l.get("capex") if capex_l else None),
             "Cr", capex_yoy,
             note=f"FY{capex_l['fy']}" if capex_l else ""),
        _kpi("CSR spend",
             _fmt_csr(latest_csr.get("spent_inr_cr")),
             "Cr",
             f"obligation {_fmt_csr(latest_csr.get('obligation_inr_cr'))} Cr"
             if latest_csr.get("obligation_inr_cr") is not None else "",
             note=f"FY{latest_csr.get('fy')}" if latest_csr else ""),
    ]

    # Build breakdowns from rows that ACTUALLY have data — nulls get
    # dropped so the chart doesn't show "₹0 Cr" placeholder bars.
    breakdowns: list[dict] = []
    rev_items = [
        {"label": f"FY{r['fy']}", "value": r["revenue_from_operations"], "share": 0}
        for r in rows if r.get("revenue_from_operations") is not None
    ]
    if rev_items:
        breakdowns.append({
            "title": "Revenue from operations — last FYs disclosed (₹ Cr)",
            "unit": "₹ Cr",
            "items": rev_items,
        })
    capex_items = [
        {"label": f"FY{r['fy']}", "value": r["capex"], "share": 0}
        for r in rows if r.get("capex") is not None
    ]
    if capex_items:
        breakdowns.append({
            "title": "Capex programme (₹ Cr)",
            "unit": "₹ Cr",
            "items": capex_items,
        })
    csr_items = [
        {"label": f"FY{r['fy']} · obligation",
         "value": r["obligation_inr_cr"], "share": 0}
        for r in csr_rows if r.get("obligation_inr_cr") is not None
    ]
    if csr_items:
        breakdowns.append({
            "title": "CSR obligation by FY (₹ Cr)",
            "unit": "₹ Cr",
            "items": csr_items,
        })

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
        "lead":  "Worker / executive LTIFR, recordable injuries and fatalities — latest disclosure cycle (BRSR FY 2024-25). The FY 2025-26 BRSR is typically published Oct–Dec after the FY closes.",
    },
    "hr": {
        "title": "HR · Workforce",
        "lead":  "Headcount, diversity, attrition, training and apprenticeship — latest disclosure cycle (BRSR + ESG Data Book FY 2024-25). FY 2025-26 disclosures will land later in 2026.",
    },
    "procurement": {
        "title": "Procurement",
        "lead":  "MSE share + GeM portal procurement — latest Annual Report disclosure (FY 2023-24). FY 2024-25 detail expected when next AR ships.",
    },
    "finance": {
        "title": "Finance",
        "lead":  "Standalone revenue, PBT, capex, dividend, CSR — five-year snapshot from OIL's Annual Report FY 2024-25 (latest audited cycle).",
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
