"""Platform-to-reference calibration on 8-day windows.

Unit of analysis: (region, year, 8-day window). The value is the sum over the window of the
platform's daily unique active 1 km cells ("cell-days"). Each link maps one platform's value to
the reference platform's value (VIIRS S-NPP). Models are simple and interpretable; the model is
chosen by blocked cross-validation inside the training years only. Test years are scored once.
"""
from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import HuberRegressor

from backend import config

HARM = config.PROCESSED / "harmonized"
CAL = config.PROCESSED / "calibrated"

REFERENCE = "SNPP"
# name, x platform, y platform, training period, test period (inclusive dates), purpose
LINKS = [
    {"name": "MODIS_to_SNPP", "x": "MODIS", "y": "SNPP", "train": ("2012-02-01", "2021-12-31"),
     "test": ("2022-01-01", "2025-12-31"), "use": "Jul 2002 - Jan 2012"},
    {"name": "Terra_to_SNPP", "x": "Terra", "y": "SNPP", "train": ("2012-02-01", "2021-12-31"),
     "test": ("2022-01-01", "2025-12-31"), "use": "Nov 2000 - Jul 2002"},
    {"name": "Terra_to_MODIS", "x": "Terra", "y": "MODIS", "train": ("2003-01-01", "2014-12-31"),
     "test": ("2015-01-01", "2025-12-31"), "use": "diagnostic: 2002 Aqua transition"},
    {"name": "NOAA20_to_SNPP", "x": "NOAA20", "y": "SNPP", "train": ("2018-04-01", "2022-12-31"),
     "test": ("2023-01-01", "2025-12-31"), "use": "secondary carrier after S-NPP"},
    {"name": "NOAA21_to_SNPP", "x": "NOAA21", "y": "SNPP", "train": ("2023-03-01", "2024-12-31"),
     "test": ("2025-01-01", "2026-07-31"), "use": "primary carrier after S-NPP"},
]
MODELS = ["ratio", "month_ratio", "region_ratio", "region_season_ratio", "loglinear_month",
          "loglinear_month_scaled"]
MAX_CV_BIAS_PCT = 5.0  # a model must reproduce training-period totals within this in cross-validation
SHRINK = 50.0     # pseudo cell-days pulling sparse region/season ratios toward the pooled ratio
MIN_SUPPORT = 50  # minimum summed x for a month/region ratio before falling back to the pooled ratio
PI = (0.10, 0.90)  # 80 % prediction interval
BINS = [-0.5, 0.5, 5, 25, 100, np.inf]


def season_of(month):
    return (np.asarray(month) % 12) // 3  # 0=DJF, 1=MAM, 2=JJA, 3=SON


def window_table(pdaily: pd.DataFrame, value: str = "cells") -> pd.DataFrame:
    """Sum daily values into fixed 8-day windows (46 per year, the last one shorter)."""
    d = pdaily[["aoi_id", "date", "platform", value]].copy()
    d["year"] = d["date"].dt.year
    d["win"] = (d["date"].dt.day_of_year - 1) // 8
    w = d.groupby(["aoi_id", "year", "win", "platform"], observed=True)[value].sum().unstack("platform", fill_value=0)
    return w


def full_windows(aois, start: str, end: str) -> pd.DataFrame:
    """All (aoi, year, window) units that lie entirely inside [start, end]."""
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    rows = []
    for y in range(s.year, e.year + 1):
        for k in range(46):
            ws = pd.Timestamp(date(y, 1, 1)) + pd.Timedelta(days=8 * k)
            we = min(ws + pd.Timedelta(days=7), pd.Timestamp(date(y, 12, 31)))
            if ws >= s and we <= e:
                rows.append((y, k, (ws + pd.Timedelta(days=3)).month))
    base = pd.DataFrame(rows, columns=["year", "win", "month"])
    return pd.concat([base.assign(aoi_id=a) for a in aois], ignore_index=True)


def link_frame(w: pd.DataFrame, link: dict, aois, period: tuple) -> pd.DataFrame:
    f = full_windows(aois, *period)
    idx = pd.MultiIndex.from_frame(f[["aoi_id", "year", "win"]])
    for col, plat in (("x", link["x"]), ("y", link["y"])):
        f[col] = (w[plat].reindex(idx).fillna(0).to_numpy() if plat in w.columns else 0.0)
    f["season"] = season_of(f["month"])
    return f


# ----------------------------------------------------------------------------- models
def fit(model: str, f: pd.DataFrame) -> dict:
    x, y = f["x"].to_numpy(float), f["y"].to_numpy(float)
    pos = x > 0
    k = float(y[pos].sum() / x[pos].sum()) if x[pos].sum() > 0 else 1.0
    p = {"model": model, "k": k, "c0": float(y[~pos].mean()) if (~pos).any() else 0.0}
    c0m = f[~pos].groupby("month")["y"].mean()
    p["c0_month"] = {int(m): float(v) for m, v in c0m.items()}
    if model == "month_ratio":
        g = f[pos].groupby("month")[["x", "y"]].sum()
        p["k_month"] = {int(m): float(r.y / r.x) for m, r in g.iterrows() if r.x >= MIN_SUPPORT}
    elif model == "region_ratio":
        g = f[pos].groupby("aoi_id")[["x", "y"]].sum()
        p["k_region"] = {a: float((r.y + SHRINK * k) / (r.x + SHRINK)) for a, r in g.iterrows()}
    elif model == "region_season_ratio":
        g = f[pos].groupby("aoi_id")[["x", "y"]].sum()
        kr = {a: float((r.y + SHRINK * k) / (r.x + SHRINK)) for a, r in g.iterrows()}
        p["k_region"] = kr
        gs = f[pos].groupby(["aoi_id", "season"])[["x", "y"]].sum()
        p["k_region_season"] = {f"{a}|{int(s)}": float((r.y + SHRINK * kr[a]) / (r.x + SHRINK))
                                for (a, s), r in gs.iterrows()}
    elif model in ("loglinear_month", "loglinear_month_scaled"):
        months = sorted(f["month"].unique())
        X = np.column_stack([np.log1p(x)] + [(f["month"].to_numpy() == m).astype(float) for m in months])
        h = HuberRegressor(fit_intercept=False, alpha=1e-4, max_iter=1000).fit(X, np.log1p(y))
        p["b"] = float(h.coef_[0])
        p["a_month"] = {int(m): float(c) for m, c in zip(months, h.coef_[1:])}
        p["scale"] = 1.0
        if model == "loglinear_month_scaled":
            # A log-space fit underestimates or overestimates totals when transformed back.
            # Rescale so the fitted total equals the observed total in the fitting data.
            raw = np.clip(np.expm1(X @ h.coef_), 0, None)
            p["scale"] = float(y.sum() / raw.sum()) if raw.sum() > 0 else 1.0
    return p


def predict(p: dict, x, month, aoi_id) -> np.ndarray:
    x = np.asarray(x, float)
    month = np.broadcast_to(np.asarray(month), x.shape)
    aoi = np.broadcast_to(np.asarray(aoi_id, dtype=object), x.shape)
    m = p["model"]
    if m in ("loglinear_month", "loglinear_month_scaled"):
        a_default = float(np.mean(list(p["a_month"].values())))
        a = np.array([p["a_month"].get(int(v), a_default) for v in month.ravel()]).reshape(x.shape)
        return p.get("scale", 1.0) * np.clip(np.expm1(a + p["b"] * np.log1p(x)), 0, None)
    k = np.full(x.shape, p["k"])
    if m == "month_ratio":
        k = np.array([p["k_month"].get(int(v), p["k"]) for v in month.ravel()]).reshape(x.shape)
    elif m == "region_ratio":
        k = np.array([p["k_region"].get(a, p["k"]) for a in aoi.ravel()]).reshape(x.shape)
    elif m == "region_season_ratio":
        s = season_of(month)
        k = np.array([p["k_region_season"].get(f"{a}|{int(q)}", p["k_region"].get(a, p["k"]))
                      for a, q in zip(aoi.ravel(), np.ravel(s))]).reshape(x.shape)
    c0 = np.array([p["c0_month"].get(int(v), p["c0"]) for v in month.ravel()]).reshape(x.shape)
    return np.where(x > 0, k * x, c0)


# ----------------------------------------------------------------------------- scoring
def metrics(y, yhat, lo=None, hi=None) -> dict:
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    out = {"n": int(len(y)), "n_nonzero_ref": int((y > 0).sum()),
           "mae": float(np.mean(np.abs(yhat - y))), "rmse": float(np.sqrt(np.mean((yhat - y) ** 2))),
           "mean_bias": float(np.mean(yhat - y)), "mean_ref": float(np.mean(y)),
           "total_bias_pct": float(100 * (yhat.sum() / y.sum() - 1)) if y.sum() > 0 else None,
           "log_mae": float(np.mean(np.abs(np.log1p(yhat) - np.log1p(y)))),
           "spearman": float(spearmanr(y, yhat).statistic) if len(y) > 2 and y.std() > 0 and yhat.std() > 0 else None}
    if lo is not None:
        out["interval_coverage_pct"] = float(100 * np.mean((y >= lo) & (y <= hi)))
    return out


def year_folds(years, n_folds: int = 5):
    ys = sorted(set(years))
    return [list(part) for part in np.array_split(ys, min(n_folds, len(ys)))]


def cross_validate(f: pd.DataFrame) -> tuple[dict, np.ndarray, str]:
    """Blocked CV over training years. Returns scores, out-of-fold predictions of the best model, its name."""
    oof = {m: np.full(len(f), np.nan) for m in MODELS}
    for held in year_folds(f["year"]):
        te = f["year"].isin(held).to_numpy()
        tr = ~te
        if tr.sum() == 0:
            continue
        for m in MODELS:
            p = fit(m, f[tr])
            oof[m][te] = predict(p, f.loc[te, "x"], f.loc[te, "month"], f.loc[te, "aoi_id"])
    scores = {}
    for m in MODELS:
        ok = ~np.isnan(oof[m])
        scores[m] = metrics(f.loc[ok, "y"], oof[m][ok])
    # Selection uses training-year cross-validation only: first require that the model
    # reproduces totals (no systematic over/under-estimation), then prefer the lowest log error.
    ok = [m for m in MODELS if scores[m]["total_bias_pct"] is not None
          and abs(scores[m]["total_bias_pct"]) <= MAX_CV_BIAS_PCT]
    best = min(ok or MODELS, key=lambda m: scores[m]["log_mae"])
    return scores, oof[best], best


def residual_quantiles(y, yhat) -> dict:
    """Log-space residual quantiles by size of the prediction, for prediction intervals."""
    r = np.log1p(np.asarray(y, float)) - np.log1p(np.asarray(yhat, float))
    b = np.digitize(yhat, BINS[1:-1], right=True)
    q = {}
    for i in range(len(BINS) - 1):
        sel = b == i
        if sel.sum() >= 20:
            q[str(i)] = [float(np.quantile(r[sel], PI[0])), float(np.quantile(r[sel], PI[1])), int(sel.sum())]
    q["all"] = [float(np.quantile(r, PI[0])), float(np.quantile(r, PI[1])), int(len(r))]
    return q


def interval(yhat, q: dict):
    yhat = np.asarray(yhat, float)
    b = np.digitize(yhat, BINS[1:-1], right=True)
    lo_r = np.array([q.get(str(i), q["all"])[0] for i in b.ravel()]).reshape(yhat.shape)
    hi_r = np.array([q.get(str(i), q["all"])[1] for i in b.ravel()]).reshape(yhat.shape)
    lo = np.clip(np.expm1(np.log1p(yhat) + lo_r), 0, None)
    hi = np.clip(np.expm1(np.log1p(yhat) + hi_r), 0, None)
    return lo, hi


def region_ids(pdaily: pd.DataFrame) -> list[str]:
    return sorted(a for a in pdaily["aoi_id"].unique() if "-ADM1-" in a)


def build() -> dict:
    CAL.mkdir(parents=True, exist_ok=True)
    pdaily = pd.read_parquet(HARM / "platform_daily.parquet")
    regions = region_ids(pdaily)
    country = [a for a in pdaily["aoi_id"].unique() if "-ADM" not in a]
    w = window_table(pdaily[pdaily["aoi_id"].isin(regions + country)])
    avail = {p: (s["date"].min(), s["date"].max()) for p, s in pdaily.groupby("platform")}
    out, summary = {"reference": REFERENCE, "links": {}}, {}
    for link in LINKS:
        if link["x"] not in avail or link["y"] not in avail:
            out["links"][link["name"]] = {"status": "no_data", **link}
            summary[link["name"]] = "no data"
            continue
        # Clip periods to dates where both platforms actually delivered data.
        lo = max(avail[link["x"]][0], avail[link["y"]][0])
        hi = min(avail[link["x"]][1], avail[link["y"]][1])
        tr_p = (max(pd.Timestamp(link["train"][0]), lo), min(pd.Timestamp(link["train"][1]), hi))
        te_p = (max(pd.Timestamp(link["test"][0]), lo), min(pd.Timestamp(link["test"][1]), hi))
        ftr = link_frame(w, link, regions, tr_p)
        fte = link_frame(w, link, regions, te_p)
        if len(ftr) < 100 or (ftr["x"] > 0).sum() < 50 or len(fte) < 50:
            out["links"][link["name"]] = {"status": "insufficient_overlap", **link,
                                          "train_windows": len(ftr), "test_windows": len(fte)}
            summary[link["name"]] = "insufficient overlap"
            continue
        cv, oof, best = cross_validate(ftr)
        params = fit(best, ftr)
        q = residual_quantiles(ftr["y"], oof)
        # Country-level ratio for country-wide application (fitted on training period only).
        fc = link_frame(w, link, country, tr_p)
        params["k_region"] = {**params.get("k_region", {}),
                              **{country[0]: float(fc["y"].sum() / fc["x"].sum()) if fc["x"].sum() > 0 else params["k"]}} \
            if best in ("region_ratio", "region_season_ratio") else params.get("k_region")
        if params.get("k_region") is None:
            params.pop("k_region")
        # Final, single scoring on the held-out test years.
        test_scores = {}
        for m in MODELS:
            pm = params if m == best else fit(m, ftr)
            yh = predict(pm, fte["x"], fte["month"], fte["aoi_id"])
            if m == best:
                lo_i, hi_i = interval(yh, q)
                test_scores[m] = metrics(fte["y"], yh, lo_i, hi_i)
            else:
                test_scores[m] = metrics(fte["y"], yh)
        test_scores["uncalibrated"] = metrics(fte["y"], fte["x"])
        yh_best = predict(params, fte["x"], fte["month"], fte["aoi_id"])
        by_year = {int(y): metrics(g["y"], yh_best[(fte["year"] == y).to_numpy()])
                   for y, g in fte.groupby("year")}
        by_region = {a: metrics(g["y"], yh_best[(fte["aoi_id"] == a).to_numpy()])
                     for a, g in fte.groupby("aoi_id")}
        out["links"][link["name"]] = {
            "status": "fitted", **link, "train_period": [str(tr_p[0].date()), str(tr_p[1].date())],
            "test_period": [str(te_p[0].date()), str(te_p[1].date())],
            "train_windows": int(len(ftr)), "train_windows_x_nonzero": int((ftr["x"] > 0).sum()),
            "test_windows": int(len(fte)), "regions": regions, "chosen_model": best,
            "cv_scores_training_years": cv, "test_scores": test_scores,
            "test_by_year": by_year, "test_by_region": by_region, "params": params,
            "residual_quantiles": q, "interval": list(PI)}
        summary[link["name"]] = {"model": best, "k": round(params["k"], 3),
                                 "test_mae": round(test_scores[best]["mae"], 2),
                                 "test_bias_pct": round(test_scores[best]["total_bias_pct"], 1),
                                 "test_spearman": round(test_scores[best]["spearman"], 3),
                                 "coverage": round(test_scores[best]["interval_coverage_pct"], 1),
                                 "uncal_bias_pct": round(test_scores["uncalibrated"]["total_bias_pct"], 1)}
    (CAL / "calibration.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return summary


def load() -> dict:
    return json.loads((CAL / "calibration.json").read_text(encoding="utf-8"))
