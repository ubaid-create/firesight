"""FireSight API. Run:  .venv/Scripts/python -m uvicorn backend.api.main:app --port 8000

All numbers are read from the processed NASA FIRMS datasets; nothing is synthesised.
"""
from __future__ import annotations

import csv
import io
import json
import time
from datetime import date, timedelta

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import config
from backend.api import data as D
from backend.services import custom_aoi, stories

def _clean(o):
    """Make any result JSON-safe: NaN/inf become null, numpy and pandas scalars become Python types."""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, pd.Timestamp):
        return o.isoformat()
    return o


class SafeJSON(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(_clean(content), allow_nan=False, separators=(",", ":")).encode("utf-8")


app = FastAPI(title="FireSight API", version="1.0", default_response_class=SafeJSON)
app.add_middleware(GZipMiddleware, minimum_size=2000)

METHOD_CODE = {"no_source": 0, "reference_observed": 1, "calibrated_terra": 2, "calibrated_modis": 3,
               "calibrated_noaa21": 4, "calibrated_noaa20": 5}
ANOM_CODE = {"insufficient_baseline": 0, "normal": 1, "unusually_low": 2, "elevated": 3, "highly_unusual": 4}
RAW_PLATFORMS = ["Terra", "Aqua", "MODIS", "SNPP", "NOAA20", "NOAA21"]


def frame(aoi: str) -> pd.DataFrame:
    try:
        return D.harmonized(aoi)
    except KeyError:
        info = D.aoi_info(aoi)
        if info and not info.get("harmonized"):
            raise HTTPException(409, "No processed historical record for this area (coverage: not acquired).")
        raise HTTPException(404, f"unknown AOI {aoi}")


def parse_date(s: str | None, default=None) -> pd.Timestamp | None:
    if s is None:
        return default
    try:
        return pd.Timestamp(s)
    except Exception:
        raise HTTPException(400, f"invalid date {s!r}")


def latest_date(f: pd.DataFrame) -> pd.Timestamp:
    return f.loc[f["h_roll"].notna(), "date"].max()


# ----------------------------------------------------------------------------- metadata
@app.get("/api/meta")
def meta():
    cal = D.calibration()
    av = D.availability()
    pak = D.harmonized("PAK")
    links = {n: {"status": l["status"], "x": l["x"], "y": l["y"], "use": l.get("use"),
                 "chosen_model": l.get("chosen_model"), "train_period": l.get("train_period"),
                 "test_period": l.get("test_period"),
                 "test_total_bias_pct": l["test_scores"][l["chosen_model"]]["total_bias_pct"] if l["status"] == "fitted" else None,
                 "uncalibrated_total_bias_pct": l["test_scores"]["uncalibrated"]["total_bias_pct"] if l["status"] == "fitted" else None,
                 "test_spearman": l["test_scores"][l["chosen_model"]]["spearman"] if l["status"] == "fitted" else None,
                 "interval_coverage_pct": l["test_scores"][l["chosen_model"]].get("interval_coverage_pct") if l["status"] == "fitted" else None}
             for n, l in cal["links"].items()}
    m = D.missing()
    return {
        "app": "FireSight", "calibration_version": cal["version"], "reference": cal["reference"],
        "latest_date": str(latest_date(pak).date()), "first_date": str(pak["date"].min().date()),
        "platforms": [{"platform": r.platform, "label": D.PLATFORM_LABEL[r.platform], "processing": r.processing,
                       "first": str(pd.Timestamp(r.first).date()), "last": str(pd.Timestamp(r.last).date()),
                       "detections": int(r.detections)} for r in av.itertuples()],
        "links": links,
        "carrier_periods": [
            {"from": "2000-11-01", "to": "2002-07-05", "carrier": "Terra", "method": "calibrated_terra"},
            {"from": "2002-07-06", "to": "2012-01-26", "carrier": "MODIS (Terra+Aqua)", "method": "calibrated_modis"},
            {"from": "2012-01-27", "to": "2026-11-02", "carrier": "VIIRS S-NPP", "method": "reference_observed"},
            {"from": "2026-11-03", "to": str(latest_date(pak).date()), "carrier": "VIIRS NOAA-21", "method": "calibrated_noaa21"}],
        "missing_data": {f"{p}/{proc}": int(n) for (p, proc), n in m.groupby(["platform", "processing"]).size().items()},
        "sources": [
            {"name": "NASA FIRMS country archive (MODIS C6.1, VIIRS S-NPP, VIIRS NOAA-20)", "url": "https://firms.modaps.eosdis.nasa.gov/country/"},
            {"name": "NASA FIRMS Area API (NOAA-21 standard, 2026 standard and near-real-time)", "url": "https://firms.modaps.eosdis.nasa.gov/api/area/"},
            {"name": "NASA FIRMS missing-data table", "url": "https://firms.modaps.eosdis.nasa.gov/api/missing_data/"},
            {"name": "geoBoundaries gbOpen PAK ADM0-2 (2019, public domain)", "url": "https://www.geoboundaries.org/"}],
    }


@app.get("/api/aois")
def list_aois():
    a = D.aois()
    out = []
    for r in a.itertuples():
        out.append({"aoi_id": r.aoi_id, "name": r.name, "level": r.level, "parent": r.parent,
                    "area_km2": round(float(r.area_km2), 1), "bounds": [r.west, r.south, r.east, r.north],
                    "rating": r.rating, "has_index": bool(r.has_index)})
    for s in stories.STORIES:
        info = D.aoi_info(s["aoi_id"])
        if info and info["level"] == "CUSTOM":
            out.append({"aoi_id": info["aoi_id"], "name": info["name"], "level": "STORY", "parent": s.get("parent_aoi"),
                        "area_km2": round(info["area_km2"], 1), "bounds": info["bounds"],
                        "rating": info["reliability"]["rating"], "has_index": True})
    return out


@app.get("/api/aoi/{aoi_id}")
def get_aoi(aoi_id: str):
    info = D.aoi_info(aoi_id)
    if info is None:
        raise HTTPException(404, "unknown AOI")
    return info


@app.get("/api/geo/{level}")
def geo(level: str):
    if level not in ("adm0", "adm1", "adm2"):
        raise HTTPException(404)
    return FileResponse(config.PROCESSED / "web" / f"{level}.geojson", media_type="application/geo+json")


# ----------------------------------------------------------------------------- calendar
@app.get("/api/calendar")
def calendar(aoi: str = "PAK", measure: str = Query("h8", pattern="^(h8|raw)$"), platform: str = "SNPP"):
    f = frame(aoi)
    n = len(f)
    flags = D.missing_flags()
    if measure == "h8":
        val, lo, hi = f["h_roll"], f["h_roll_lo"], f["h_roll_hi"]
        idx = f["index_roll"]
        method = f["method"].map(METHOD_CODE).fillna(0).astype(int)
        carrier = f["carrier"]
        gap = np.array([bool(flags.get(c, flags["none"]).get(d, False)) for c, d in zip(carrier, f["date"])])
        prov = f["provisional"].astype(int)
        an, z = f["anomaly"].map(ANOM_CODE).fillna(0).astype(int), f["z"]
        zero = (f["carrier_cells_8d"] == 0) & f["h_roll"].notna()
        label = "Harmonized activity (8-day rolling, VIIRS S-NPP-equivalent active 1 km cells per day)"
    else:
        if platform not in RAW_PLATFORMS:
            raise HTTPException(400, "unknown platform")
        val = f[f"cells_{platform}"]
        lo = hi = val
        idx = pd.Series(np.nan, index=f.index)
        method = pd.Series(np.where(val.notna(), 1, 0), index=f.index)
        fl = flags.get(platform, flags["none"])
        gap = np.array([bool(fl.get(d, False)) for d in f["date"]]) if platform != "MODIS" else \
            np.array([bool(flags["MODIS"].get(d, False)) for d in f["date"]])
        prov = pd.Series(0, index=f.index)
        an = pd.Series(0, index=f.index)
        z = pd.Series(np.nan, index=f.index)
        zero = (val == 0)
        label = f"Raw observed active 1 km cells per day — {D.PLATFORM_LABEL[platform]} (not harmonized)"
    return {
        "aoi": aoi, "measure": measure, "platform": platform if measure == "raw" else None, "label": label,
        "start": str(f["date"].iloc[0].date()), "n": n,
        "value": D.nan_to_none(val, 2), "lo": D.nan_to_none(lo, 2), "hi": D.nan_to_none(hi, 2),
        "index": D.nan_to_none(idx, 0), "method": method.astype(int).tolist(),
        "zero": zero.fillna(False).astype(int).tolist(), "gap": gap.astype(int).tolist(),
        "provisional": pd.Series(prov).astype(int).tolist(), "anomaly": pd.Series(an).astype(int).tolist(),
        "z": D.nan_to_none(z, 2),
        "codes": {"method": {v: k for k, v in METHOD_CODE.items()}, "anomaly": {v: k for k, v in ANOM_CODE.items()}},
    }


# ----------------------------------------------------------------------------- day detail
def platform_obs(aoi: str, day: pd.Timestamp) -> list[dict]:
    if aoi.startswith(("CUSTOM-", "STORY-")):
        where, params, geom = D.aoi_filter_sql(aoi)
        d = D.q(f"""select platform, lat, lon, frp, daynight, conf_class, det_type, cell, persist_class
                    from read_parquet('{D.DETS}') where date = ? and {where}""", [day] + params)
        d = D.clip(d, geom)
        d = d[(d["det_type"] <= 0) & d["conf_class"].isin(["nominal", "high"])]
        out = []
        for p in D.PLATFORMS:
            s = d[d["platform"] == p]
            out.append({"platform": p, "n_det": int(len(s)), "cells": int(s["cell"].nunique()),
                        "frp_mean": float(s["frp"].mean()) if len(s) else None, "frp_max": float(s["frp"].max()) if len(s) else None,
                        "n_day": int((s["daynight"] == "D").sum()), "n_night": int((s["daynight"] == "N").sum())})
        return out
    p = D.q(f"select * from read_parquet('{D.PDAILY}') where aoi_id = ? and date = ?", [aoi, day])
    out = []
    for pl in D.PLATFORMS:
        r = p[p["platform"] == pl]
        if r.empty:
            out.append({"platform": pl, "n_det": 0, "cells": 0, "frp_mean": None, "frp_max": None, "n_day": 0, "n_night": 0})
            continue
        r = r.iloc[0]
        out.append({"platform": pl, "n_det": int(r["n_det"]), "cells": int(r["cells"]),
                    "n_det_all": int(r["n_det_all"]), "n_unclassified": int(r["n_unclassified"]),
                    "frp_mean": None if pd.isna(r["frp_mean"]) else float(r["frp_mean"]),
                    "frp_max": None if pd.isna(r["frp_max"]) else float(r["frp_max"]),
                    "n_day": int(r["n_day"]), "n_night": int(r["n_night"]),
                    "conf": {"low": int(r["n_conf_low"]), "nominal": int(r["n_conf_nominal"]), "high": int(r["n_conf_high"])},
                    "has_nrt": bool(r["has_nrt"])})
    return out


@app.get("/api/day")
def day_detail(aoi: str = "PAK", date: str = Query(...)):
    f = frame(aoi)
    d = parse_date(date)
    row = f[f["date"] == d]
    if row.empty:
        raise HTTPException(404, "date outside the record")
    r = row.iloc[0]
    av = D.availability()
    delivering = sorted({x.platform for x in av.itertuples() if pd.Timestamp(x.first) <= d <= pd.Timestamp(x.last)})
    miss = D.missing()
    missing_today = miss[pd.to_datetime(miss["date"]) == d][["platform", "processing"]].to_dict("records")
    num = lambda v, nd=2: None if pd.isna(v) else round(float(v), nd)  # noqa: E731
    return {
        "aoi": aoi, "date": str(d.date()), "platforms": platform_obs(aoi, d), "delivering": delivering,
        "missing_today": missing_today,
        "harmonized": {"h_roll": num(r["h_roll"]), "lo": num(r["h_roll_lo"]), "hi": num(r["h_roll_hi"]),
                       "index": num(r["index_roll"], 0), "carrier": r["carrier"], "method": r["method"],
                       "provisional": bool(r["provisional"]), "carrier_cells_8d": num(r["carrier_cells_8d"]),
                       "naive_roll": num(r["naive_roll"]), "eq_modis_roll": num(r["eq_modis_roll"]),
                       "snpp_roll": num(r["snpp_roll"])},
        "anomaly": {"label": r["anomaly"], "z": num(r["z"]), "method": r["anomaly_method"],
                    "base_median": num(r["base_median"]), "base_mad": num(r["base_mad"]),
                    "base_years": int(r["base_years"])},
    }


# ----------------------------------------------------------------------------- map layers
def hotspot_query(aoi, start, end, platforms, daynight, modis_conf, viirs_conf, types, persist, limit):
    s, e = parse_date(start), parse_date(end)
    if (e - s).days > 400:
        raise HTTPException(400, "date range limited to 400 days for the map")
    where, params, geom = D.aoi_filter_sql(aoi)
    plats = [p for p in platforms.split(",") if p in D.PLATFORMS]
    dn = [x for x in daynight.split(",") if x in ("D", "N")]
    mc = [x for x in modis_conf.split(",") if x in ("low", "nominal", "high")]
    vc = [x for x in viirs_conf.split(",") if x in ("low", "nominal", "high")]
    ty = [int(x) for x in types.split(",") if x in ("-1", "0", "1", "2", "3")]
    pc = [x for x in persist.split(",") if x in ("normal", "suspected_persistent", "known_static")]
    if not (plats and dn and ty and pc):
        return pd.DataFrame(), 0
    ph = lambda xs: ",".join("?" * len(xs)) if xs else "NULL"  # noqa: E731
    sql = f"""from read_parquet('{D.DETS}') where date between ? and ? and {where}
              and platform in ({ph(plats)}) and daynight in ({ph(dn)}) and det_type in ({ph(ty)})
              and persist_class in ({ph(pc)})
              and ((instrument = 'MODIS' and conf_class in ({ph(mc)})) or (instrument = 'VIIRS' and conf_class in ({ph(vc)})))"""
    args = [s, e] + params + plats + dn + ty + pc + mc + vc
    total = int(D.q("select count(*) as n " + sql, args)["n"].iloc[0])
    d = D.q(f"""select det_id, lat, lon, platform, date, acq_hhmm, frp, conf_raw, conf_class, daynight, det_type,
                persist_class, processing, scan_km, track_km {sql} order by frp desc limit {int(limit)}""", args)
    return D.clip(d, geom), total


@app.get("/api/hotspots")
def hotspots(aoi: str = "PAK", start: str = Query(...), end: str = Query(...),
             platforms: str = "Terra,Aqua,SNPP,NOAA20,NOAA21", daynight: str = "D,N",
             modis_conf: str = "nominal,high", viirs_conf: str = "nominal,high", types: str = "0,-1",
             persist: str = "normal,suspected_persistent,known_static", limit: int = Query(40000, le=80000)):
    d, total = hotspot_query(aoi, start, end, platforms, daynight, modis_conf, viirs_conf, types, persist, limit)
    if d.empty:
        return {"total": total, "returned": 0, "truncated": False, "cols": {}}
    return {"total": total, "returned": int(len(d)), "truncated": total > len(d),
            "cols": {"id": d["det_id"].astype(int).tolist(), "lat": d["lat"].round(5).tolist(), "lon": d["lon"].round(5).tolist(),
                     "p": d["platform"].tolist(), "frp": d["frp"].round(1).fillna(0).tolist(),
                     "dn": d["daynight"].tolist(), "date": d["date"].dt.strftime("%Y-%m-%d").tolist(),
                     "pc": d["persist_class"].tolist(), "nrt": (d["processing"] == "NRT").astype(int).tolist()}}


@app.get("/api/hotspot/{det_id}")
def hotspot(det_id: int):
    d = D.q(f"select * from read_parquet('{D.DETS}') where det_id = ?", [det_id])
    if d.empty:
        raise HTTPException(404)
    r = d.iloc[0].to_dict()
    out = {}
    for k, v in r.items():
        if isinstance(v, pd.Timestamp):
            v = v.isoformat()
        elif isinstance(v, (np.floating, float)):
            v = None if np.isnan(v) else round(float(v), 4)
        elif isinstance(v, np.integer):
            v = int(v)
        out[k] = v
    out["platform_label"] = D.PLATFORM_LABEL.get(out["platform"], out["platform"])
    out["type_label"] = {-1: "not provided (near-real-time)", 0: "presumed vegetation fire", 1: "active volcano",
                         2: "other static land source", 3: "offshore"}.get(out["det_type"], "unknown")
    return out


@app.get("/api/grid")
def grid(aoi: str = "PAK", start: str = Query(...), end: str = Query(...),
         platforms: str = "Terra,Aqua,SNPP,NOAA20,NOAA21", size: float = Query(0.1, ge=0.02, le=0.5)):
    s, e = parse_date(start), parse_date(end)
    where, params, geom = D.aoi_filter_sql(aoi)
    plats = [p for p in platforms.split(",") if p in D.PLATFORMS] or ["SNPP"]
    d = D.q(f"""select lon, lat, cell, date, platform from read_parquet('{D.DETS}')
                where date between ? and ? and {where} and platform in ({",".join("?" * len(plats))})
                and det_type <= 0 and conf_class in ('nominal','high')""", [s, e] + params + plats)
    d = D.clip(d, geom)
    if d.empty:
        return {"size": size, "lon": [], "lat": [], "value": [], "unit": "active 1 km cell-days per bin"}
    d["bx"] = np.floor(d["lon"] / size).astype(int)
    d["by"] = np.floor(d["lat"] / size).astype(int)
    g = d.drop_duplicates(["bx", "by", "cell", "date", "platform"]).groupby(["bx", "by", "platform"]).size().reset_index(name="n")
    g = g.groupby(["bx", "by"])["n"].sum().reset_index()
    return {"size": size, "lon": (g["bx"] * size).round(4).tolist(), "lat": (g["by"] * size).round(4).tolist(),
            "value": g["n"].astype(int).tolist(),
            "unit": "active 1 km cell-days per bin, summed over the selected platforms (raw, not harmonized)"}


@app.get("/api/choropleth")
def choropleth(level: str = Query("ADM2", pattern="^(ADM1|ADM2)$"), date: str = Query(...)):
    d = parse_date(date)
    f = D.q(f"""select aoi_id, h_roll, h_roll_lo, h_roll_hi, index_roll, anomaly, carrier, provisional
                from read_parquet('{D.HARM}') where date = ? and aoi_id like ?""", [d, f"PAK-{level}-%"])
    rel = D.aois().set_index("aoi_id")["rating"]
    area = D.aois().set_index("aoi_id")["area_km2"]
    return {"date": str(d.date()), "level": level, "items": [
        {"aoi_id": r.aoi_id, "h_roll": None if pd.isna(r.h_roll) else round(float(r.h_roll), 2),
         "density_per_1000km2": None if pd.isna(r.h_roll) else round(1000 * float(r.h_roll) / float(area[r.aoi_id]), 3),
         "index": None if pd.isna(r.index_roll) else int(r.index_roll), "anomaly": str(r.anomaly),
         "carrier": str(r.carrier), "provisional": bool(r.provisional), "rating": rel.get(r.aoi_id)} for r in f.itertuples()]}


# ----------------------------------------------------------------------------- series and analytics
@app.get("/api/series")
def series(aoi: str = "PAK", freq: str = Query("month", pattern="^(8d|month|year)$"),
           start: str | None = None, end: str | None = None):
    f = frame(aoi).copy()
    if start:
        f = f[f["date"] >= parse_date(start)]
    if end:
        f = f[f["date"] <= parse_date(end)]
    if freq == "8d":
        key = f["date"].dt.year.astype(str) + "-" + ((f["date"].dt.day_of_year - 1) // 8).astype(str).str.zfill(2)
    elif freq == "month":
        key = f["date"].dt.strftime("%Y-%m")
    else:
        key = f["date"].dt.strftime("%Y")
    f["k"] = key
    g = f.groupby("k", sort=True)

    def mean_full(col):
        return g[col].apply(lambda s: s.mean() if s.notna().all() else np.nan)

    out = {"aoi": aoi, "freq": freq, "unit": "mean active 1 km cells per day",
           "period": g["date"].min().dt.strftime("%Y-%m-%d").tolist(), "observed": {}}
    for p in RAW_PLATFORMS + ["ALL"]:
        out["observed"][p] = D.nan_to_none(mean_full(f"cells_{p}"), 2)
    out["harmonized"] = D.nan_to_none(g["h_roll"].mean(), 2)
    out["harmonized_lo"] = D.nan_to_none(g["h_roll_lo"].mean(), 2)
    out["harmonized_hi"] = D.nan_to_none(g["h_roll_hi"].mean(), 2)
    out["calibrated_modis"] = D.nan_to_none(g["eq_modis_roll"].mean(), 2)
    out["calibrated_noaa20"] = D.nan_to_none(g["eq_noaa20_roll"].mean(), 2)
    out["calibrated_noaa21"] = D.nan_to_none(g["eq_noaa21_roll"].mean(), 2)
    out["reconstructed_share"] = D.nan_to_none(g["method"].apply(lambda s: float(s.str.startswith("calibrated").mean())), 2)
    out["provisional_share"] = D.nan_to_none(g["provisional"].mean(), 2)
    return out


@app.get("/api/seasonal")
def seasonal(aoi: str = "PAK", start_year: int = 2001, end_year: int = 2025):
    f = frame(aoi)
    f = f[(f["date"].dt.year >= start_year) & (f["date"].dt.year <= end_year)]
    m = f.groupby([f["date"].dt.year, f["date"].dt.month])["h_roll"].mean().unstack()
    return {"aoi": aoi, "years": [int(y) for y in m.index], "months": list(range(1, 13)),
            "median": D.nan_to_none(m.median(axis=0), 2), "p25": D.nan_to_none(m.quantile(0.25, axis=0), 2),
            "p75": D.nan_to_none(m.quantile(0.75, axis=0), 2), "min": D.nan_to_none(m.min(axis=0), 2),
            "max": D.nan_to_none(m.max(axis=0), 2),
            "by_year": {int(y): D.nan_to_none(r, 2) for y, r in m.iterrows()},
            "unit": "mean harmonized active cells per day (S-NPP scale)"}


@app.get("/api/anomalies")
def anomalies(aoi: str = "PAK", top: int = 25, start: str | None = None, end: str | None = None):
    f = frame(aoi)
    if start:
        f = f[f["date"] >= parse_date(start)]
    if end:
        f = f[f["date"] <= parse_date(end)]
    flag = f["anomaly"].isin(["elevated", "highly_unusual"]).to_numpy()
    eps, i = [], 0
    dates = f["date"].to_numpy()
    while i < len(f):
        if not flag[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(f) and flag[j + 1]:
            j += 1
        seg = f.iloc[i:j + 1]
        pk = seg["h_roll"].idxmax()
        r = f.loc[pk]
        eps.append({"start": str(pd.Timestamp(dates[i]).date()), "end": str(pd.Timestamp(dates[j]).date()), "days": int(j - i + 1),
                    "peak_date": str(r["date"].date()), "peak": round(float(r["h_roll"]), 2),
                    "peak_lo": round(float(r["h_roll_lo"]), 2), "peak_hi": round(float(r["h_roll_hi"]), 2),
                    "base_median": None if pd.isna(r["base_median"]) else round(float(r["base_median"]), 2),
                    "z_max": None if seg["z"].isna().all() else round(float(seg["z"].max()), 2),
                    "label": "highly_unusual" if (seg["anomaly"] == "highly_unusual").any() else "elevated",
                    "method": r["anomaly_method"], "carrier": r["carrier"], "reconstructed": r["method"].startswith("calibrated"),
                    "provisional": bool(seg["provisional"].any()),
                    "excess": None if pd.isna(r["base_median"]) else round(float(r["h_roll"] - r["base_median"]), 2)})
        i = j + 1
    eps.sort(key=lambda e: (e["excess"] or 0), reverse=True)
    yr = f.assign(y=f["date"].dt.year).groupby("y")["anomaly"].value_counts().unstack(fill_value=0)
    return {"aoi": aoi, "episodes": eps[:top], "episodes_total": len(eps),
            "days_by_year": {int(y): {k: int(v) for k, v in r.items()} for y, r in yr.iterrows()},
            "thresholds": {"elevated_z": 2.0, "highly_unusual_z": 3.5, "unusually_low_z": -2.0,
                           "baseline": "same day of year ±7 days in all other years, minimum 5 years",
                           "min_activity": "at least 5 harmonized cell-days in the 8-day window to be flagged"}}


@app.get("/api/windows")
def windows(aoi: str = "PAK"):
    if aoi.startswith(("CUSTOM-", "STORY-")):
        m = custom_aoi.load_meta(aoi) or {}
        return {"aoi": aoi, "windows": m.get("windows", []), "weekly": m.get("weekly", []), "info": m.get("windows_info", {})}
    w = pd.read_parquet(config.PROCESSED / "harmonized" / "critical_windows.parquet")
    st = pd.read_parquet(config.PROCESSED / "harmonized" / "weekly_stats.parquet", filters=[("aoi_id", "==", aoi)])
    w = w[w["aoi_id"] == aoi]
    return {"aoi": aoi, "windows": w.drop(columns=["aoi_id"]).to_dict("records"),
            "weekly": st.drop(columns=["aoi_id"]).to_dict("records"),
            "info": {"threshold": float(st["threshold"].iloc[0]) if len(st) else None,
                     "rule": "a week is elevated in a year when its harmonized weekly total exceeds the 75th percentile of "
                             "all active weeks for this area; a week is critical when elevated in at least half of the years"}}


@app.get("/api/compare")
def compare(aoi: str = "PAK", days: int = Query(14, ge=7, le=60), end: str | None = None):
    f = frame(aoi).set_index("date")
    e = parse_date(end, latest_date(f.reset_index()))
    s = e - pd.Timedelta(days=days - 1)
    cur = f.loc[s:e]
    if len(cur) < days or cur["h_roll"].isna().any():
        raise HTTPException(409, "the selected period is not fully covered")
    hist = []
    for y in range(f.index.min().year, e.year):
        try:
            ys = pd.Timestamp(year=y, month=s.month, day=min(s.day, 28) if s.month == 2 and s.day == 29 else s.day)
        except ValueError:
            continue
        ye = ys + pd.Timedelta(days=days - 1)
        h = f.loc[ys:ye]
        if len(h) == days and h["h_roll"].notna().all():
            hist.append({"year": y, "mean": float(h["h_roll"].mean()), "method": h["method"].mode().iloc[0]})
    if len(hist) < 5:
        raise HTTPException(409, "fewer than 5 comparable historical years")
    vals = np.array([x["mean"] for x in hist])
    med = float(np.median(vals))
    c = float(cur["h_roll"].mean())
    obs = np.array([x["mean"] for x in hist if x["method"] == "reference_observed"])
    observed = None
    if len(obs) >= 5:
        om = float(np.median(obs))
        observed = {"median": round(om, 2), "years": int(len(obs)),
                    "pct_difference": None if om == 0 else round(100 * (c / om - 1), 1),
                    "rank": int((obs < c).sum()) + 1}
    raw = {p: (None if cur[f"cells_{p}"].isna().all() else round(float(cur[f"cells_{p}"].mean()), 2)) for p in RAW_PLATFORMS}
    return {"aoi": aoi, "start": str(s.date()), "end": str(e.date()), "days": days,
            "current": round(c, 2), "current_lo": round(float(cur["h_roll_lo"].mean()), 2),
            "current_hi": round(float(cur["h_roll_hi"].mean()), 2),
            "historical_median": round(med, 2), "historical_p25": round(float(np.percentile(vals, 25)), 2),
            "historical_p75": round(float(np.percentile(vals, 75)), 2),
            "pct_difference": None if med == 0 else round(100 * (c / med - 1), 1),
            "rank": int((vals < c).sum()) + 1, "years_used": len(hist), "history": hist,
            "observed_era": observed,
            "provisional_days": int(cur["provisional"].sum()), "carriers": cur["carrier"].value_counts().to_dict(),
            "raw_current_by_platform": raw,
            "unit": "mean harmonized active cells per day (S-NPP scale) over the same calendar dates in each year"}


@app.get("/api/summary")
def summary(aoi: str = "PAK"):
    f = frame(aoi)
    info = D.aoi_info(aoi)
    last = latest_date(f)
    full = f[(f["date"].dt.year >= 2001) & (f["date"].dt.year <= 2025)]
    yr = full.groupby(full["date"].dt.year)["h_roll"].mean()
    mo = full.groupby(full["date"].dt.month)["h_roll"].mean()
    pk = f.loc[f["h_roll"].idxmax()] if f["h_roll"].notna().any() else None
    recent = f[f["date"] > last - pd.Timedelta(days=365)]
    an = recent["anomaly"].value_counts().to_dict()
    lr = f[f["date"] == last].iloc[0]
    return {"aoi": aoi, "info": info, "latest_date": str(last.date()), "first_date": str(f["date"].min().date()),
            "mean_activity_2001_2025": None if yr.empty else round(float(yr.mean()), 2),
            "most_active_year": None if yr.empty or yr.isna().all() else {"year": int(yr.idxmax()), "mean": round(float(yr.max()), 2)},
            "least_active_year": None if yr.empty or yr.isna().all() else {"year": int(yr.idxmin()), "mean": round(float(yr.min()), 2)},
            "most_active_month": None if mo.isna().all() else {"month": int(mo.idxmax()), "mean": round(float(mo.max()), 2)},
            "peak": None if pk is None else {"date": str(pk["date"].date()), "value": round(float(pk["h_roll"]), 2),
                                             "carrier": pk["carrier"], "method": pk["method"]},
            "last_365_anomaly_days": {k: int(v) for k, v in an.items()},
            "latest": {"date": str(last.date()), "h_roll": round(float(lr["h_roll"]), 2), "index": None if pd.isna(lr["index_roll"]) else int(lr["index_roll"]),
                       "carrier": lr["carrier"], "method": lr["method"], "provisional": bool(lr["provisional"]),
                       "anomaly": lr["anomaly"]},
            "days_by_method": f["method"].value_counts().to_dict()}


@app.get("/api/validation")
def validation_view():
    v = D.validation()
    rel = D.aois()
    return {"links": meta()["links"],
            "transitions": v["exp2_transitions"], "scales": v["exp3_scales"], "sensitivity": v["exp6_sensitivity"],
            "geographic": v["exp7_geographic"], "correspondence": v["exp8_correspondence"], "raw": v["exp1_raw"],
            "test_by_year": {n: l.get("test_by_year") for n, l in v["links"].items()},
            "candidates": {n: {"chosen": l.get("chosen_model"), "cv": l.get("cv_scores_training_years"), "test": l.get("test_scores")}
                           for n, l in v["links"].items() if l.get("status") == "fitted"},
            "reliability_counts": {f"{a}/{b}": int(n) for (a, b), n in rel.groupby(["level", "rating"]).size().items()},
            "generated": v.get("generated")}


# ----------------------------------------------------------------------------- stories
@app.get("/api/stories")
def list_stories():
    out = []
    for s in stories.STORIES:
        d = {k: v for k, v in s.items() if k != "custom_polygon"}
        try:
            f = frame(s["aoi_id"])
            w = f[(f["date"] >= s["start"]) & (f["date"] <= s["end"])]
            where, params, geom = D.aoi_filter_sql(s["aoi_id"])
            det = D.q(f"""select platform, date, frp from read_parquet('{D.DETS}') where date between ? and ? and {where}
                         and det_type <= 0 and conf_class in ('nominal','high')""",
                      [pd.Timestamp(s["start"]), pd.Timestamp(s["end"])] + params)
            if geom is not None:
                det = D.clip(D.q(f"""select platform, date, frp, lat, lon from read_parquet('{D.DETS}') where date between ? and ? and {where}
                                     and det_type <= 0 and conf_class in ('nominal','high')""",
                                 [pd.Timestamp(s["start"]), pd.Timestamp(s["end"])] + params), geom)
            pk = w.loc[w["h_roll"].idxmax()] if w["h_roll"].notna().any() else None
            d["stats"] = {
                "detections_by_platform": det.groupby("platform").size().astype(int).to_dict(),
                "first_detection": None if det.empty else str(pd.Timestamp(det["date"].min()).date()),
                "last_detection": None if det.empty else str(pd.Timestamp(det["date"].max()).date()),
                "max_frp": None if det.empty else round(float(det["frp"].max()), 1),
                "peak_date": None if pk is None else str(pk["date"].date()),
                "peak_h_roll": None if pk is None else round(float(pk["h_roll"]), 2),
                "peak_index": None if pk is None or pd.isna(pk["index_roll"]) else int(pk["index_roll"]),
                "anomaly_days": w["anomaly"].value_counts().to_dict(),
                "max_z": None if w["z"].isna().all() else round(float(w["z"].max()), 2)}
        except HTTPException:
            d["stats"] = None
        out.append(d)
    return out


# ----------------------------------------------------------------------------- custom AOIs, on-demand
class CustomAOI(BaseModel):
    type: str
    bbox: list[float] | None = None
    coordinates: list[list[float]] | None = None
    name: str | None = None


@app.post("/api/custom")
def create_custom(spec: CustomAOI):
    try:
        t = time.time()
        meta_ = custom_aoi.create(spec.model_dump(exclude_none=True), name=spec.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    D.harmonized.cache_clear()
    meta_ = {k: v for k, v in meta_.items() if k not in ("weekly",)}
    meta_["seconds"] = round(time.time() - t, 1)
    return meta_


_ONDEMAND: dict = {}


@app.get("/api/ondemand")
def ondemand(bbox: str = Query(..., description="west,south,east,north"), days: int = Query(5, ge=1, le=10)):
    """Recent raw FIRMS NRT observations for any area. Uncalibrated and provisional; nothing is harmonized."""
    from backend.ingestion import data_downloader as dl
    try:
        w, s, e, n = (float(v) for v in bbox.split(","))
    except Exception:
        raise HTTPException(400, "bbox must be west,south,east,north")
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90) or (e - w) * (n - s) > 100:
        raise HTTPException(400, "bounding box invalid or larger than 100 square degrees")
    key = config.load_map_key()
    if not key:
        raise HTTPException(503, "FIRMS MAP_KEY not configured on the server")
    ck = (round(w, 3), round(s, 3), round(e, 3), round(n, 3), days)
    if ck in _ONDEMAND and time.time() - _ONDEMAND[ck][0] < 1800:
        return _ONDEMAND[ck][1]
    rows = []
    errors = []
    end_d = date.today()
    for src, plat in (("MODIS_NRT", None), ("VIIRS_NOAA20_NRT", "NOAA20"), ("VIIRS_NOAA21_NRT", "NOAA21")):
        cur = end_d - timedelta(days=days - 1)
        while cur <= end_d:
            k = min(5, (end_d - cur).days + 1)
            try:
                text = dl.api_get_text(f"/api/area/csv/{key}/{src}/{w},{s},{e},{n}/{k}/{cur.isoformat()}", key, max_attempts=3)
                df = pd.read_csv(io.StringIO(text), dtype=str)
                if len(df):
                    df["source"] = src
                    rows.append(df)
            except Exception as ex:  # report, never expose the key
                errors.append(f"{src} {cur}: {dl.redact(str(ex), key)[:120]}")
            cur += timedelta(days=k)
    from backend.processing.normalizer import parse_frame
    if rows:
        frames = []
        for df in rows:
            frames.append(parse_frame(df, df["source"].iloc[0], "NRT"))
        d = pd.concat(frames, ignore_index=True)
    else:
        d = pd.DataFrame(columns=["lat", "lon", "platform", "date", "frp", "daynight", "conf_class"])
    res = {"bbox": [w, s, e, n], "days": days, "coverage": "on_demand_raw", "harmonized": False,
           "note": "Recent near-real-time FIRMS observations retrieved on demand. Provisional, uncalibrated; "
                   "no historical record or harmonized score is available for this area.",
           "errors": errors, "total": int(len(d)),
           "by_platform": d.groupby("platform").size().astype(int).to_dict() if len(d) else {},
           "cols": {"lat": d["lat"].round(5).tolist(), "lon": d["lon"].round(5).tolist(), "p": d["platform"].astype(str).tolist(),
                    "frp": pd.to_numeric(d["frp"]).round(1).fillna(0).tolist(), "dn": d["daynight"].astype(str).tolist(),
                    "date": pd.to_datetime(d["date"]).dt.strftime("%Y-%m-%d").tolist(),
                    "pc": ["normal"] * len(d), "nrt": [1] * len(d), "id": [-1] * len(d)}}
    _ONDEMAND[ck] = (time.time(), res)
    return res


# ----------------------------------------------------------------------------- export
@app.get("/api/export.csv")
def export_csv(aoi: str = "PAK", start: str | None = None, end: str | None = None,
               kind: str = Query("harmonized", pattern="^(harmonized|detections)$")):
    cal = D.calibration()
    info = D.aoi_info(aoi) or {}
    s = parse_date(start, pd.Timestamp("2000-11-01"))
    e = parse_date(end, pd.Timestamp("2100-01-01"))
    buf = io.StringIO()
    if kind == "harmonized":
        f = frame(aoi)
        f = f[(f["date"] >= s) & (f["date"] <= e)]
        cols = ["date", "h_roll", "h_roll_lo", "h_roll_hi", "index_roll", "carrier", "method", "provisional",
                "carrier_cells_8d", "anomaly", "z", "anomaly_method", "base_median", "base_mad", "base_years",
                "cells_Terra", "cells_Aqua", "cells_MODIS", "cells_SNPP", "cells_NOAA20", "cells_NOAA21", "cells_ALL",
                "eq_modis_roll", "eq_noaa20_roll", "eq_noaa21_roll", "snpp_roll", "naive_roll"]
        out = f[cols].copy()
        out["date"] = out["date"].dt.strftime("%Y-%m-%d")
        out.insert(0, "aoi_name", info.get("name"))
        out.insert(0, "aoi_id", aoi)
        out["reliability_rating"] = (info.get("reliability") or {}).get("rating")
        out["calibration_version"] = cal["version"]
        out["reference_scale"] = "VIIRS S-NPP active 1 km cells per day (8-day rolling mean)"
        out.to_csv(buf, index=False, float_format="%.3f")
        name = f"firesight_{aoi}_harmonized.csv"
    else:
        if (e - s).days > 400:
            raise HTTPException(400, "detection export limited to 400 days")
        where, params, geom = D.aoi_filter_sql(aoi)
        d = D.clip(D.q(f"select * from read_parquet('{D.DETS}') where date between ? and ? and {where} order by ts_utc",
                       [s, e] + params), geom)
        d["calibration_version"] = cal["version"]
        d.to_csv(buf, index=False, quoting=csv.QUOTE_MINIMAL)
        name = f"firesight_{aoi}_detections_{s.date()}_{e.date()}.csv"
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/health")
def health():
    return {"ok": True}


# ----------------------------------------------------------------------------- static frontend
DIST = config.ROOT / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        target = DIST / path
        if path and target.is_file():
            return FileResponse(target)
        return FileResponse(DIST / "index.html")


@app.exception_handler(KeyError)
def key_error(_req, exc):
    return JSONResponse({"detail": f"not found: {exc}"}, status_code=404)
