"""Read-only data access for the API (DuckDB over Parquet, small in-memory caches)."""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache

import duckdb
import numpy as np
import pandas as pd
import shapely

from backend import config
from backend.services import custom_aoi

P = config.PROCESSED
HARM = (P / "harmonized" / "harmonized_daily.parquet").as_posix()
PDAILY = (P / "harmonized" / "platform_daily.parquet").as_posix()
DETS = (P / "web" / "detections_web.parquet").as_posix()
PLATFORMS = ["Terra", "Aqua", "SNPP", "NOAA20", "NOAA21"]
PLATFORM_LABEL = {"Terra": "MODIS Terra", "Aqua": "MODIS Aqua", "SNPP": "VIIRS S-NPP", "NOAA20": "VIIRS NOAA-20",
                  "NOAA21": "VIIRS NOAA-21", "MODIS": "MODIS (Terra+Aqua)", "ALL": "All platforms (naive union)"}
MODIS_SET = {"Terra", "Aqua"}


def q(sql: str, params: list | None = None) -> pd.DataFrame:
    con = duckdb.connect()
    try:
        return con.execute(sql, params or []).df()
    finally:
        con.close()


@lru_cache(maxsize=1)
def aois() -> pd.DataFrame:
    a = pd.read_parquet(P / "normalized" / "aois.parquet")
    b = pd.read_parquet(P / "web" / "aoi_bounds.parquet")
    r = pd.read_parquet(P / "web" / "aoi_reliability.parquet").drop(columns=["level", "name"])
    a = a.merge(b, on="aoi_id", how="left").merge(r, on="aoi_id", how="left")
    a1 = a[a["level"] == "ADM1"].set_index("index")["aoi_id"].to_dict()
    a["parent"] = [a1.get(int(x)) if lv == "ADM2" and pd.notna(x) else ("PAK" if lv == "ADM1" else None)
                   for lv, x in zip(a["level"], a["adm1"])]
    return a


def _num(v, kind=float):
    return None if v is None or pd.isna(v) else kind(v)


def aoi_info(aoi_id: str) -> dict | None:
    a = aois()
    row = a[a["aoi_id"] == aoi_id]
    if len(row):
        r = row.iloc[0]
        return {"aoi_id": aoi_id, "name": r["name"], "level": r["level"], "area_km2": float(r["area_km2"]),
                "bounds": [r["west"], r["south"], r["east"], r["north"]], "parent": r["parent"],
                "index": int(r["index"]), "coverage": "pakistan_processed", "harmonized": True,
                "reliability": {"rating": r["rating"], "test_spearman": _num(r["test_spearman"]),
                                "test_windows_active": _num(r["test_windows_active"], int),
                                "test_interval_coverage_pct": _num(r["test_interval_coverage_pct"])}}
    m = custom_aoi.load_meta(aoi_id)
    if m is None:
        return None
    return {k: m.get(k) for k in ("aoi_id", "name", "level", "area_km2", "bounds", "coverage", "harmonized",
                                  "reliability", "note", "geometry", "share_inside_pakistan")}


@lru_cache(maxsize=48)
def harmonized(aoi_id: str) -> pd.DataFrame:
    if aoi_id.startswith(("CUSTOM-", "STORY-")):
        f = custom_aoi.load_frame(aoi_id)
        if f is None:
            raise KeyError(aoi_id)
    else:
        f = q(f"select * from read_parquet('{HARM}') where aoi_id = ? order by date", [aoi_id])
        if f.empty:
            raise KeyError(aoi_id)
    f["date"] = pd.to_datetime(f["date"])
    for c in ("carrier", "method", "anomaly", "anomaly_method"):
        f[c] = f[c].astype(str)
    return f.reset_index(drop=True)


@lru_cache(maxsize=1)
def missing() -> pd.DataFrame:
    path = P / "web" / "missing_data.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame(columns=["date", "platform", "processing"])


@lru_cache(maxsize=1)
def missing_flags() -> dict:
    """Per platform: True when FIRMS lists missing data within the 8-day window ending on that day."""
    m = missing()
    idx = pd.date_range("2000-11-01", "2026-12-31", freq="D")
    out = {}
    for p in PLATFORMS:
        s = pd.Series(0, index=idx)
        s[s.index.isin(pd.to_datetime(m.loc[m["platform"] == p, "date"]))] = 1
        out[p] = s.rolling(8, min_periods=1).max().astype(bool)
    out["MODIS"] = out["Terra"] | out["Aqua"]
    out["none"] = pd.Series(False, index=idx)
    return out


@lru_cache(maxsize=1)
def calibration() -> dict:
    raw = (P / "calibrated" / "calibration.json").read_bytes()
    return {"version": hashlib.sha256(raw).hexdigest()[:12], **json.loads(raw)}


@lru_cache(maxsize=1)
def validation() -> dict:
    return json.loads((config.ROOT / "validation" / "results.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def availability() -> pd.DataFrame:
    return q(f"""select platform, processing, min(date) as first, max(date) as last, count(*) as detections
                 from read_parquet('{DETS}') group by 1, 2 order by 1, 2""")


def aoi_filter_sql(aoi_id: str):
    """SQL predicate for detections in an AOI, plus an optional geometry for exact clipping."""
    info = aoi_info(aoi_id)
    if info is None:
        raise KeyError(aoi_id)
    if info["level"] == "ADM0":
        return "true", [], None
    if info["level"] == "ADM1":
        return "adm1 = ?", [info["index"]], None
    if info["level"] == "ADM2":
        return "adm2 = ?", [info["index"]], None
    w, s, e, n = info["bounds"]
    return "lon between ? and ? and lat between ? and ?", [w, e, s, n], shapely.geometry.shape(info["geometry"])


def clip(df: pd.DataFrame, geom) -> pd.DataFrame:
    if geom is None or df.empty:
        return df
    return df[shapely.contains_xy(geom, df["lon"].to_numpy(), df["lat"].to_numpy())]


def nan_to_none(a, nd: int = 3) -> list:
    arr = np.asarray(a, dtype=float)
    return [None if np.isnan(v) else round(float(v), nd) for v in arr]
