"""Grid aggregation: cell-day table, persistent-source classes and per-platform daily metrics.

Platforms are never summed. Two derived groups are added for analysis only:
  MODIS = union of Terra and Aqua active cells (the long-record MODIS series)
  ALL   = union of every platform's cells (the "naive merge", used to show its bias)
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from backend import config

NORM = config.PROCESSED / "normalized"
GRID = config.PROCESSED / "gridded"
HARM = config.PROCESSED / "harmonized"

# Persistent-source heuristics (documented, adjustable; nothing is deleted on this basis).
STATIC_TYPE_SHARE = 0.5      # share of typed detections flagged type 1/2/3 -> known static
PERSIST_MIN_YEARS = 8        # distinct years with activity
PERSIST_MIN_MONTHS = 10      # distinct calendar months with activity
PERSIST_MAX_MONTH_SHARE = 0.25  # busiest calendar month holds at most this share of active days


def load_detections() -> pd.DataFrame:
    d = pd.read_parquet(NORM / "detections.parquet")
    d["cell"] = (d["cell_y"].astype("int64") + 10_000) * 100_000 + (d["cell_x"].astype("int64") + 20_000)
    d["cell2"] = ((d["cell_y"] // 2).astype("int64") + 10_000) * 100_000 + ((d["cell_x"] // 2).astype("int64") + 20_000)
    typed = d["det_type"].notna()
    d["untyped"] = ~typed
    d["static_type"] = typed & (d["det_type"] != 0)
    d["type_ok"] = ~d["static_type"]                       # type 0, or unknown (kept and flagged)
    d["conf_ok"] = d["conf_class"].isin(["nominal", "high"])
    d["default"] = d["type_ok"] & d["conf_ok"]
    d["is_nrt"] = d["processing"] == "NRT"
    d["platform"] = d["platform"].astype(str)
    return d


def classify_cells(d: pd.DataFrame) -> pd.DataFrame:
    """Persistence class per 1 km cell from detection types and recurrence."""
    g = d.groupby("cell")
    c = g.agg(n_det=("det_id", "size"), n_typed=("untyped", lambda s: int((~s).sum())),
              n_static_type=("static_type", "sum"), cell_x=("cell_x", "first"), cell_y=("cell_y", "first"),
              adm1=("adm1", "first"), adm2=("adm2", "first"))
    days = d.drop_duplicates(["cell", "date"])[["cell", "date"]]
    days["year"] = days["date"].dt.year
    days["month"] = days["date"].dt.month
    gd = days.groupby("cell")
    c["active_days"] = gd.size()
    c["years_active"] = gd["year"].nunique()
    c["months_active"] = gd["month"].nunique()
    month_counts = days.groupby(["cell", "month"]).size()
    c["max_month_share"] = (month_counts.groupby("cell").max() / c["active_days"]).astype("float32")
    share = np.where(c["n_typed"] > 0, c["n_static_type"] / c["n_typed"].clip(lower=1), 0.0)
    c["static_type_share"] = share.astype("float32")
    known = c["static_type_share"] >= STATIC_TYPE_SHARE
    suspected = (~known) & (c["years_active"] >= PERSIST_MIN_YEARS) & (c["months_active"] >= PERSIST_MIN_MONTHS) \
        & (c["max_month_share"] <= PERSIST_MAX_MONTH_SHARE)
    c["persist_class"] = np.where(known, "known_static", np.where(suspected, "suspected_persistent", "normal"))
    return c.reset_index()


def with_groups(d: pd.DataFrame) -> pd.DataFrame:
    """Append the derived MODIS and ALL platform groups as extra rows."""
    modis = d[d["platform"].isin(["Terra", "Aqua"])].copy()
    modis["platform"] = "MODIS"
    allp = d.copy()
    allp["platform"] = "ALL"
    return pd.concat([d, modis, allp], ignore_index=True)


def platform_daily(d: pd.DataFrame, key: str) -> pd.DataFrame:
    """Daily metrics per AOI key and platform. ``d`` must already contain group rows."""
    by = [key, "date", "platform"]
    out = d.groupby(by, observed=True).agg(
        n_det_all=("det_id", "size"), n_unclassified=("untyped", "sum"), n_static_type=("static_type", "sum"),
        n_overpass=("acq_hhmm", "nunique"), has_nrt=("is_nrt", "max"))
    t = d[d["type_ok"]]
    conf = t.groupby(by + ["conf_class"], observed=True).size().unstack("conf_class", fill_value=0)
    for c in ("low", "nominal", "high"):
        out[f"n_conf_{c}"] = conf[c] if c in conf.columns else 0
    out["cells_incl_low"] = t.drop_duplicates(by + ["cell"]).groupby(by, observed=True).size()
    q = d[d["default"]]
    agg = q.groupby(by, observed=True).agg(
        n_det=("det_id", "size"), frp_sum=("frp", "sum"), frp_mean=("frp", "mean"),
        frp_median=("frp", "median"), frp_max=("frp", "max"),
        n_day=("daynight", lambda s: int((s == "D").sum())),
        scan_mean=("scan_km", "mean"))
    out = out.join(agg)
    out["n_night"] = out["n_det"] - out["n_day"]
    u = q.drop_duplicates(by + ["cell"])
    out["cells"] = u.groupby(by, observed=True).size()
    out["cells_day"] = q[q["daynight"] == "D"].drop_duplicates(by + ["cell"]).groupby(by, observed=True).size()
    out["cells_night"] = q[q["daynight"] == "N"].drop_duplicates(by + ["cell"]).groupby(by, observed=True).size()
    out["cells_nopersist"] = u[u["persist_class"] == "normal"].groupby(by, observed=True).size()
    out["cells_2km"] = q.drop_duplicates(by + ["cell2"]).groupby(by, observed=True).size()
    out["cells_nadir"] = q[q["near_nadir"]].drop_duplicates(by + ["cell"]).groupby(by, observed=True).size()
    out = out.reset_index().rename(columns={key: "aoi_key"})
    count_cols = [c for c in out.columns if c.startswith(("n_", "cells"))]
    out[count_cols] = out[count_cols].fillna(0).astype("int32")
    return out


def build(iso3: str = "PAK") -> dict:
    GRID.mkdir(parents=True, exist_ok=True)
    HARM.mkdir(parents=True, exist_ok=True)
    d = load_detections()
    rep = {"detections": len(d), "default_filter_rows": int(d["default"].sum())}

    cells = classify_cells(d)
    cells.to_parquet(GRID / "cell_class.parquet", index=False)
    rep["cells"] = len(cells)
    rep["persist_class_counts"] = cells["persist_class"].value_counts().to_dict()
    d = d.merge(cells[["cell", "persist_class"]], on="cell", how="left")
    # Near-real-time rows carry no detection type. Where the standard archive already shows the
    # cell to be a static source, the untyped row is kept in the table but left out of the default view.
    nrt_static = d["untyped"] & (d["persist_class"] == "known_static")
    d.loc[nrt_static, "default"] = False
    rep["untyped_rows"] = int(d["untyped"].sum())
    rep["untyped_rows_in_known_static_cells_excluded_from_default"] = int(nrt_static.sum())
    # Near-nadir flag for the scan-angle sensitivity test: pixel no wider than 1.5x nominal.
    nominal = np.where(d["instrument"] == "MODIS", 1.0, 0.375)
    d["near_nadir"] = d["scan_km"] <= 1.5 * nominal

    # Cell-day table: what each platform saw in each cell on each day (default filter only).
    q = d[d["default"]]
    cd = q.groupby(["cell", "date", "platform"], observed=True).agg(
        n_det=("det_id", "size"), frp_max=("frp", "max"), cell_x=("cell_x", "first"), cell_y=("cell_y", "first"),
        adm1=("adm1", "first"), adm2=("adm2", "first"), lst_min=("local_solar_hour", "min"),
        lst_max=("local_solar_hour", "max"), is_nrt=("is_nrt", "max")).reset_index()
    cd.to_parquet(GRID / "cell_day.parquet", index=False)
    rep["cell_day_rows"] = len(cd)

    g = with_groups(d)
    g["k0"] = iso3
    g["k1"] = iso3 + "-ADM1-" + g["adm1"].astype(str)
    g["k2"] = iso3 + "-ADM2-" + g["adm2"].astype(str)
    parts = [platform_daily(g, "k0"), platform_daily(g, "k1"), platform_daily(g[g["adm2"] >= 0], "k2")]
    pdaily = pd.concat(parts, ignore_index=True).rename(columns={"aoi_key": "aoi_id"})
    pdaily.to_parquet(HARM / "platform_daily.parquet", index=False)
    rep["platform_daily_rows"] = len(pdaily)

    # Consistency checks.
    c0 = pdaily[pdaily["aoi_id"] == iso3]
    direct = q.drop_duplicates(["date", "platform", "cell"]).groupby("platform", observed=True).size()
    table = c0[~c0["platform"].isin(["MODIS", "ALL"])].groupby("platform")["cells"].sum()
    rep["check_country_cells_match_recount"] = bool((direct.sort_index() == table.sort_index()).all())
    piv = c0.pivot(index="date", columns="platform", values="cells").fillna(0)
    rep["check_modis_le_terra_plus_aqua"] = bool((piv["MODIS"] <= piv["Terra"] + piv["Aqua"]).all())
    rep["check_modis_ge_each"] = bool(((piv["MODIS"] >= piv["Terra"]) & (piv["MODIS"] >= piv["Aqua"])).all())
    rep["platform_date_ranges"] = {p: [str(s["date"].min().date()), str(s["date"].max().date())]
                                   for p, s in c0.groupby("platform")}
    (HARM / "aggregate_report.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    return rep
