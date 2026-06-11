"""Real predictive models for the Production & Exploration dashboards.

Every function is a PURE model over arrays the caller pulls from OIL's
own Excel files — no hidden state, no network. Each is wrapped so a
numerical failure returns ``None`` rather than 500-ing the dashboard;
the metrics layer renders a graceful "—" when a model declines to fit.

Models implemented (all genuinely computed, not curated):
  * Arps exponential decline on the mature base + workover-offset
  * OLS regression of crude production on workover count
  * Lagged multivariate OLS: production ~ workovers(t,t-1) + dev wells(t-1)
  * Monte-Carlo 2P / RRR trajectory under accretion scenarios
  * Reserve Life Index (2P / annual production)
  * Energy-mix (gas share of MMToE) linear crossover to 50%
  * Beta-Binomial Bayesian update of frontier exploration success
  * Andaman reserves sensitivity (illustrative pool sizes vs 2P gas)

Unit conventions: crude 1 MMT ≈ 1.0 MMToE; natural gas 1 BCM ≈ 0.90
MMToE (≈ BP conversion). Gas MMSCM ÷ 1000 = BCM.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
from loguru import logger

GAS_BCM_TO_MMTOE = 0.90
CRUDE_MMT_TO_MMTOE = 1.0


def _arr(xs: Sequence) -> np.ndarray:
    return np.array([float(x) for x in xs], dtype=float)


def _clean_pairs(x: Sequence, y: Sequence) -> tuple[np.ndarray, np.ndarray]:
    """Drop index positions where either series is None/NaN."""
    xs, ys = [], []
    for a, b in zip(x, y):
        if a is None or b is None:
            continue
        try:
            fa, fb = float(a), float(b)
        except (TypeError, ValueError):
            continue
        if fa != fa or fb != fb:
            continue
        xs.append(fa)
        ys.append(fb)
    return np.array(xs), np.array(ys)


# ============================================================
# Production Insight 1 — workover → production regression + decline
# ============================================================

def workover_production_model(workovers: Sequence, crude: Sequence,
                              forecast_workovers: float = 307.0,
                              hold_target_mmt: float = 3.45) -> dict | None:
    """OLS of crude (MMT) on workover count. Returns the marginal
    MMT-per-workover slope, fit quality, an FY27 point forecast at
    ``forecast_workovers`` sustained interventions, and — inverting the
    line — the workover count required to hold ``hold_target_mmt``."""
    try:
        wx, cy = _clean_pairs(workovers, crude)
        if len(wx) < 3:
            return None
        slope, intercept = np.polyfit(wx, cy, 1)
        pred = slope * wx + intercept
        ss_res = float(np.sum((cy - pred) ** 2))
        ss_tot = float(np.sum((cy - cy.mean()) ** 2)) or 1e-9
        r2 = 1.0 - ss_res / ss_tot
        fy27 = slope * forecast_workovers + intercept
        req = ((hold_target_mmt - intercept) / slope) if abs(slope) > 1e-9 else None
        return {
            "slope_mmt_per_workover": round(float(slope), 6),
            "intercept": round(float(intercept), 4),
            "r2": round(r2, 3),
            "forecast_workovers": forecast_workovers,
            "fy27_forecast_mmt": round(float(fy27), 3),
            "hold_target_mmt": hold_target_mmt,
            "required_workovers_for_target": round(float(req))
            if req is not None and np.isfinite(req) else None,
            "workover_growth_pct": round(float((wx[-1] / wx[0] - 1) * 100), 1)
            if wx[0] else None,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[predictive] workover_production_model failed: {exc}")
        return None


def exponential_decline(fys: Sequence, crude: Sequence,
                        base_years: int = 6, horizon: int = 1) -> dict | None:
    """Fit an exponential (Arps b=0) decline to the *pre-recovery* base
    window — the first ``base_years`` of the series — and project it
    forward. This is the "what the mature base does on its own, before
    the workover programme" counter-factual.

        q(t) = qi * exp(-D * t)
    """
    try:
        c = _arr([x for x in crude if x is not None])
        if len(c) < base_years:
            return None
        base = c[:base_years]
        t = np.arange(len(base))
        # log-linear fit → exponential decline rate D (per year)
        with np.errstate(divide="ignore"):
            logq = np.log(base)
        slope, b0 = np.polyfit(t, logq, 1)
        D = -float(slope)
        qi = float(np.exp(b0))
        # project from the LAST actual value forward `horizon` years at D
        last = float(c[-1])
        proj = last * np.exp(-D * np.arange(1, horizon + 1))
        return {
            "annual_decline_pct": round(D * 100, 2),
            "implied_qi_mmt": round(qi, 3),
            "base_window_fys": list(fys[:base_years]) if fys else [],
            "counterfactual_next_mmt": round(float(proj[-1]), 3),
            "last_actual_mmt": round(last, 3),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[predictive] exponential_decline failed: {exc}")
        return None


# ============================================================
# Exploration Insight 1 — lagged intervention-ROI regression
# ============================================================

def lagged_intervention_model(crude: Sequence, workovers: Sequence,
                              dev_wells: Sequence,
                              hold_target_mmt: float = 3.45) -> dict | None:
    """Multivariate OLS:  crude(t) ~ workovers(t) + devwells(t-1).

    Kept deliberately to two predictors: with only ~5 annual observations
    a 3-predictor fit saturates (R²→1) and the inversion degenerates.
    Two regressors keep degrees of freedom and a credible marginal read.
    Reports coefficients, R², and the implied current-year workovers to
    hold ``hold_target_mmt`` with the dev-well lag frozen at its latest.
    """
    try:
        c = [None if v is None else float(v) for v in crude]
        w = [None if v is None else float(v) for v in workovers]
        d = [None if v is None else float(v) for v in dev_wells]
        rows_y, rows_X = [], []
        for t in range(1, len(c)):
            if None in (c[t], w[t], d[t - 1]):
                continue
            rows_y.append(c[t])
            rows_X.append([1.0, w[t], d[t - 1]])
        if len(rows_y) < 4:
            return None
        X = np.array(rows_X)
        y = np.array(rows_y)
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        pred = X @ coef
        ss_res = float(np.sum((y - pred) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1e-9
        r2 = 1.0 - ss_res / ss_tot
        n, k = len(rows_y), X.shape[1]
        adj_r2 = 1.0 - (1.0 - r2) * (n - 1) / max(n - k, 1)
        b0, b_w, b_dlag = (float(x) for x in coef)
        d_lag = next((v for v in reversed(d) if v is not None), 0.0)
        req_workovers = None
        if abs(b_w) > 1e-9:
            req_workovers = (hold_target_mmt - b0 - b_dlag * d_lag) / b_w
        return {
            "coef_intercept": round(b0, 4),
            "coef_workover_t": round(b_w, 6),
            "coef_devwell_t_1": round(b_dlag, 6),
            "r2": round(r2, 3),
            "adj_r2": round(adj_r2, 3),
            "hold_target_mmt": hold_target_mmt,
            "required_workovers_fy27": round(float(req_workovers))
            if req_workovers is not None and np.isfinite(req_workovers) else None,
            "n_obs": n,
            "small_sample": n < 8,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[predictive] lagged_intervention_model failed: {exc}")
        return None


# ============================================================
# Production Insight 2 — RRR / 2P Monte Carlo
# ============================================================

def rrr_monte_carlo(accretion: Sequence, production_equiv: Sequence,
                    reserve_2p_latest: float, horizon: int = 3,
                    n_sims: int = 20000, seed: int = 7) -> dict | None:
    """Monte-Carlo the RRR trajectory ``horizon`` years out.

    accretion ~ Normal(historical mean, historical std); production
    grows at the historical CAGR. RRR(t) = accretion(t) / production(t).
    Reports P(RRR≥1) at the horizon and the % uplift in mean accretion
    needed to bring expected RRR back to 1.0 by then.
    """
    try:
        acc = _arr([x for x in accretion if x is not None])
        prod = _arr([x for x in production_equiv if x is not None])
        if len(acc) < 3 or len(prod) < 3:
            return None
        mu, sigma = float(acc.mean()), float(acc.std(ddof=1) or acc.mean() * 0.1)
        # production growth: geometric mean of YoY ratios
        ratios = prod[1:] / prod[:-1]
        g = float(np.exp(np.mean(np.log(ratios)))) if np.all(ratios > 0) else 1.0
        prod_last = float(prod[-1])
        rng = np.random.default_rng(seed)
        # simulate accretion path; RRR at horizon
        prod_h = prod_last * (g ** horizon)
        draws = rng.normal(mu, sigma, size=(n_sims, horizon))
        draws = np.clip(draws, 0, None)
        rrr_h = draws[:, -1] / prod_h
        p_ge1 = float(np.mean(rrr_h >= 1.0))
        # uplift to mean accretion needed for E[RRR]=1.0 at horizon
        needed_mean = prod_h
        uplift_pct = (needed_mean / mu - 1.0) * 100 if mu else None
        return {
            "hist_mean_accretion": round(mu, 3),
            "hist_std_accretion": round(sigma, 3),
            "production_cagr_pct": round((g - 1) * 100, 2),
            "horizon_years": horizon,
            "prob_rrr_ge_1_at_horizon": round(p_ge1, 3),
            "required_accretion_for_rrr1": round(float(needed_mean), 3),
            "accretion_uplift_pct": round(float(uplift_pct), 1)
            if uplift_pct is not None else None,
            "n_sims": n_sims,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[predictive] rrr_monte_carlo failed: {exc}")
        return None


def reserve_life_index(reserve_2p: float | None,
                       annual_production: float | None) -> float | None:
    try:
        if not reserve_2p or not annual_production:
            return None
        return round(float(reserve_2p) / float(annual_production), 1)
    except Exception:  # noqa: BLE001
        return None


# ============================================================
# Production Insight 3 — gasification / energy-mix crossover
# ============================================================

def energy_mix_crossover(fys: Sequence, crude_mmt: Sequence,
                         gas_mmscm: Sequence) -> dict | None:
    """Convert both streams to MMToE, compute gas's share of total each
    year, fit a line to the share, and solve for the FY where gas crosses
    50 % of output."""
    try:
        years, shares, oil_idx, gas_idx = [], [], [], []
        base_crude = base_gas = None
        for fy, cm, gm in zip(fys, crude_mmt, gas_mmscm):
            if cm is None or gm is None:
                continue
            oil_toe = float(cm) * CRUDE_MMT_TO_MMTOE
            gas_toe = (float(gm) / 1000.0) * GAS_BCM_TO_MMTOE
            tot = oil_toe + gas_toe
            if tot <= 0:
                continue
            if base_crude is None:
                base_crude, base_gas = oil_toe, gas_toe
            years.append(fy)
            shares.append(gas_toe / tot * 100.0)
            oil_idx.append(round(oil_toe / base_crude * 100, 1))
            gas_idx.append(round(gas_toe / base_gas * 100, 1))
        if len(shares) < 3:
            return None
        t = np.arange(len(shares))
        slope, intercept = np.polyfit(t, np.array(shares), 1)
        cross_year = None
        if slope > 1e-6:
            t_cross = (50.0 - intercept) / slope
            # map fractional index back to an FY label (extrapolate)
            last_start = int(years[-1].split("-")[0])
            cross_year = f"FY{(last_start + int(np.ceil(t_cross - (len(shares) - 1)))) % 100:02d}"
        return {
            "fys": list(years),
            "gas_share_pct": [round(s, 1) for s in shares],
            "latest_gas_share_pct": round(shares[-1], 1),
            "share_slope_pts_per_yr": round(float(slope), 2),
            "crossover_fy_50pct": cross_year,
            "oil_indexed": oil_idx,
            "gas_indexed": gas_idx,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[predictive] energy_mix_crossover failed: {exc}")
        return None


# ============================================================
# Exploration Insight 3 — exploration effectiveness
# ============================================================

def exploration_effectiveness(accretion: Sequence, expl_meterage: Sequence,
                              rrr_target: float = 1.0,
                              production_equiv: float | None = None) -> dict | None:
    """Accretion per exploratory metre, trended, plus the meterage/wells
    implied to reach RRR ≥ target next year."""
    try:
        a, m = _clean_pairs(accretion, expl_meterage)
        if len(a) < 2:
            return None
        eff = a / np.where(m == 0, np.nan, m) * 1e6  # MMToE per million metres
        latest_eff = float(np.nanmean(eff[-1:]))
        req_accretion = production_equiv * rrr_target if production_equiv else a.mean()
        # implied metres at latest effectiveness
        per_metre = a[-1] / m[-1] if m[-1] else None
        req_metres = (req_accretion / per_metre) if per_metre else None
        return {
            "latest_accretion_per_mn_metre": round(latest_eff, 3),
            "required_accretion_for_rrr": round(float(req_accretion), 3),
            "implied_meterage": round(float(req_metres)) if req_metres else None,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[predictive] exploration_effectiveness failed: {exc}")
        return None


# ============================================================
# Andaman — Bayesian success update + reserves sensitivity
# ============================================================

def bayesian_success_update(successes: int, trials: int,
                            prior_alpha: float = 1.0,
                            prior_beta: float = 4.0) -> dict | None:
    """Beta-Binomial update of frontier-basin success probability.

    Prior Beta(1, 4) encodes the ~1-in-5 frontier base rate. Posterior
    after observing ``successes`` of ``trials`` gas-bearing wells.
    """
    try:
        a0, b0 = float(prior_alpha), float(prior_beta)
        p0 = a0 / (a0 + b0)
        a1, b1 = a0 + successes, b0 + (trials - successes)
        p1 = a1 / (a1 + b1)
        # 90% credible interval on posterior via Beta quantiles
        from scipy.stats import beta as _beta
        lo, hi = _beta.ppf([0.05, 0.95], a1, b1)
        return {
            "prior_mean": round(p0, 3),
            "posterior_mean": round(p1, 3),
            "posterior_alpha": round(a1, 2),
            "posterior_beta": round(b1, 2),
            "cred_interval_90": [round(float(lo), 3), round(float(hi), 3)],
            "observed": f"{successes} of {trials}",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[predictive] bayesian_success_update failed: {exc}")
        return None


def andaman_reserves_sensitivity(current_2p_gas_bcm: float,
                                 annual_gas_bcm: float,
                                 pools_bcm: Sequence[float] = (10.0, 25.0, 50.0)
                                 ) -> dict | None:
    """Illustrative — for each hypothetical recoverable-gas pool size,
    the % uplift to current 2P gas and the added reserve-life years.
    Everything here is explicitly unbooked / hypothetical."""
    try:
        rows = []
        for p in pools_bcm:
            uplift = p / current_2p_gas_bcm * 100 if current_2p_gas_bcm else None
            add_life = p / annual_gas_bcm if annual_gas_bcm else None
            rows.append({
                "pool_bcm": p,
                "uplift_2p_gas_pct": round(uplift, 1) if uplift is not None else None,
                "added_reserve_life_yrs": round(add_life, 1) if add_life is not None else None,
                "hypothetical": True,
            })
        per_25 = 25.0 / current_2p_gas_bcm * 100 if current_2p_gas_bcm else None
        per_25_life = 25.0 / annual_gas_bcm if annual_gas_bcm else None
        return {
            "current_2p_gas_bcm": round(current_2p_gas_bcm, 1),
            "annual_gas_bcm": round(annual_gas_bcm, 2),
            "rows": rows,
            "per_25bcm_uplift_pct": round(per_25, 1) if per_25 else None,
            "per_25bcm_life_yrs": round(per_25_life, 1) if per_25_life else None,
            "hypothetical": True,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[predictive] andaman_reserves_sensitivity failed: {exc}")
        return None
