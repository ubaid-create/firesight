"""Precompute web-ready assets from the processed pipeline outputs.

Outputs in data/processed/web/:
  adm0.geojson, adm1.geojson, adm2.geojson   simplified boundaries with aoi_id
  detections_web.parquet                     detections + persistence class, sorted by date
  missing_data.parquet                       FIRMS "missing data" days by platform
  aoi_reliability.parquet                    held-out agreement per AOI (MODIS-calibrated vs S-NPP)
  story AOIs                                 cached through backend.services.custom_aoi
"""
from __future__ import annotations

import html
import json
import re

import numpy as np
import pandas as pd
import shapely
from scipy.stats import spearmanr

from backend import config
from backend.processing.normalizer import load_admin

WEB = config.PROCESSED / "web"
PLATFORM_NAMES = {"Suomi NPP (VIIRS)": "SNPP", "NOAA-20 (VIIRS)": "NOAA20", "NOAA-21 (VIIRS)": "NOAA21",
                  "Terra (MODIS)": "Terra", "Aqua (MODIS)": "Aqua"}


def boundaries(iso3: str = "PAK") -> dict:
    aois = pd.read_parquet(config.PROCESSED / "normalized" / "aois.parquet")
    out = {}
    for level, tol in (("ADM0", 0.01), ("ADM1", 0.005), ("ADM2", 0.003)):
        geoms, props = load_admin(level, iso3)
        feats = []
        for i, (g, p) in enumerate(zip(geoms, props)):
            aoi_id = iso3 if level == "ADM0" else f"{iso3}-{level}-{i}"
            row = aois[aois["aoi_id"] == aoi_id]
            s = shapely.simplify(g, tol, preserve_topology=True)
            feats.append({"type": "Feature", "id": i, "geometry": shapely.geometry.mapping(s),
                          "properties": {"aoi_id": aoi_id, "name": p.get("shapeName"), "level": level,
                                         "area_km2": float(row["area_km2"].iloc[0]) if len(row) else None}})
        path = WEB / f"{level.lower()}.geojson"
        path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
        out[level] = {"features": len(feats), "bytes": path.stat().st_size}
    # bounding boxes for zooming
    bb = []
    for level in ("ADM0", "ADM1", "ADM2"):
        geoms, _ = load_admin(level, iso3)
        for i, g in enumerate(geoms):
            x0, y0, x1, y1 = g.bounds
            bb.append({"aoi_id": iso3 if level == "ADM0" else f"{iso3}-{level}-{i}",
                       "west": x0, "south": y0, "east": x1, "north": y1})
    pd.DataFrame(bb).to_parquet(WEB / "aoi_bounds.parquet", index=False)
    return out


def detections_web() -> dict:
    d = pd.read_parquet(config.PROCESSED / "normalized" / "detections.parquet")
    cells = pd.read_parquet(config.PROCESSED / "gridded" / "cell_class.parquet",
                            columns=["cell", "persist_class"])
    d["cell"] = (d["cell_y"].astype("int64") + 10_000) * 100_000 + (d["cell_x"].astype("int64") + 20_000)
    d = d.merge(cells, on="cell", how="left")
    d["platform"] = d["platform"].astype(str)
    d["processing"] = d["processing"].astype(str)
    d["conf_class"] = d["conf_class"].astype(str)
    d["daynight"] = d["daynight"].astype(str)
    d["version"] = d["version"].astype(str)
    d["source_file"] = d["source_file"].astype(str)
    d["det_type"] = d["det_type"].astype("float").fillna(-1).astype("int8")  # -1 = not provided (NRT)
    d = d.sort_values(["date", "ts_utc"]).reset_index(drop=True)
    keep = ["det_id", "date", "ts_utc", "acq_hhmm", "local_solar_hour", "lat", "lon", "platform", "instrument",
            "processing", "version", "brightness", "brightness_2", "frp", "conf_raw", "conf_class", "scan_km",
            "track_km", "daynight", "det_type", "adm1", "adm2", "cell", "persist_class", "source_file", "source_row"]
    d[keep].to_parquet(WEB / "detections_web.parquet", index=False, row_group_size=50_000)
    return {"rows": len(d)}


def missing_data() -> dict:
    src = config.RAW / "missing_data" / "firms_missing_data.json"
    if not src.exists():
        return {"status": "not downloaded"}
    j = json.loads(src.read_text(encoding="utf-8"))
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", j.get("html", ""), re.S)
    recs = []
    for r in rows:
        c = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
        for date_s, sat, proc in ((c[0], c[1], "SP"), (c[2], c[3], "NRT")) if len(c) == 4 else ():
            if date_s and sat in PLATFORM_NAMES:
                recs.append({"date": pd.Timestamp(date_s), "platform": PLATFORM_NAMES[sat], "processing": proc})
    m = pd.DataFrame(recs).drop_duplicates()
    m.to_parquet(WEB / "missing_data.parquet", index=False)
    return {"rows": len(m), "by_platform": {f"{a}/{b}": int(v) for (a, b), v in m.groupby(["platform", "processing"]).size().items()}}


def reliability() -> dict:
    """Per-AOI agreement of calibrated MODIS with observed S-NPP over the held-out years.

    8-day samples every 8th day of 2022-2025. Rating thresholds are FireSight interface
    categories, documented on the method page.
    """
    hd = pd.read_parquet(config.PROCESSED / "harmonized" / "harmonized_daily.parquet",
                         columns=["aoi_id", "date", "snpp_roll", "eq_modis_roll", "eq_modis_lo", "eq_modis_hi",
                                  "index_roll", "cells_SNPP"])
    aois = pd.read_parquet(config.PROCESSED / "normalized" / "aois.parquet")
    t = hd[(hd["date"] >= "2022-01-08") & (hd["date"] <= "2025-12-31")]
    t = t[((t["date"] - pd.Timestamp("2022-01-08")).dt.days % 8) == 0]
    rows = []
    for a, g in t.groupby("aoi_id", observed=True):
        y, yh = g["snpp_roll"].to_numpy() * 8, g["eq_modis_roll"].to_numpy() * 8
        ok = ~np.isnan(y) & ~np.isnan(yh)
        y, yh = y[ok], yh[ok]
        lo, hi = g["eq_modis_lo"].to_numpy()[ok] * 8, g["eq_modis_hi"].to_numpy()[ok] * 8
        active = int((y > 0).sum())
        rho = float(spearmanr(y, yh).statistic) if active >= 10 and y.std() > 0 and yh.std() > 0 else np.nan
        cov = float(100 * np.mean((y >= lo - 1e-6) & (y <= hi + 1e-6))) if len(y) else np.nan
        bias = float(100 * (yh.sum() / y.sum() - 1)) if y.sum() > 0 else np.nan
        rows.append({"aoi_id": a, "test_windows": int(len(y)), "test_windows_active": active,
                     "test_spearman": rho, "test_interval_coverage_pct": cov, "test_total_bias_pct": bias,
                     "mean_snpp_cell_days_per_window": float(y.mean()) if len(y) else np.nan})
    r = pd.DataFrame(rows).merge(aois[["aoi_id", "level", "name"]], on="aoi_id", how="right")
    has_index = hd.groupby("aoi_id", observed=True)["index_roll"].apply(lambda s: bool(s.notna().any()))
    r["has_index"] = r["aoi_id"].map(has_index).fillna(False).astype(bool)

    def rate(row):
        if not row["has_index"]:
            return "insufficient"
        if row["level"] in ("ADM0", "ADM1") and row["test_windows_active"] >= 60:
            base = "high" if (row["test_spearman"] or 0) >= 0.8 else "moderate"
        else:
            rho = row["test_spearman"]
            if np.isnan(rho) or row["test_windows_active"] < 30:
                base = "low"
            elif rho >= 0.8:
                base = "moderate"
            elif rho >= 0.6:
                base = "low"
            else:
                base = "very_low"
        return base

    r["rating"] = r.apply(rate, axis=1)
    r.to_parquet(WEB / "aoi_reliability.parquet", index=False)
    return {"aois": len(r), "ratings": {f"{a}/{b}": int(v) for (a, b), v in r.groupby(["level", "rating"]).size().items()}}


def build() -> dict:
    WEB.mkdir(parents=True, exist_ok=True)
    rep = {"boundaries": boundaries(), "detections": detections_web(), "missing_data": missing_data(),
           "reliability": reliability()}
    from backend.services import custom_aoi, stories
    for s in stories.STORIES:
        if s.get("custom_polygon"):
            res = custom_aoi.create(s["custom_polygon"], name=s["aoi_name"], fixed_id=s["aoi_id"])
            rep.setdefault("stories", {})[s["id"]] = {k: res[k] for k in ("aoi_id", "coverage", "area_km2")}
    (WEB / "precompute_report.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    return rep
