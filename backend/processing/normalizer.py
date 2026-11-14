"""Normalize raw FIRMS files into one detection table.

Raw files are read-only inputs. Every original value needed for provenance is kept:
the raw confidence string, both brightness channels, scan/track, version, source file and row.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer

from backend import config

CELL_M = 1000.0
_TO_EA = Transformer.from_crs("EPSG:4326", "EPSG:6933", always_xy=True)
_FROM_EA = Transformer.from_crs("EPSG:6933", "EPSG:4326", always_xy=True)

PLATFORM_MAP = {"Terra": "Terra", "T": "Terra", "Aqua": "Aqua", "A": "Aqua",
                "N": "SNPP", "N20": "NOAA20", "N21": "NOAA21"}
VIIRS_CONF = {"l": "low", "low": "low", "n": "nominal", "nominal": "nominal", "h": "high", "high": "high"}


def to_cells(lon, lat):
    """Return integer 1 km cell indices (cell_x, cell_y) in EPSG:6933."""
    x, y = _TO_EA.transform(np.asarray(lon, dtype="float64"), np.asarray(lat, dtype="float64"))
    return np.floor(x / CELL_M).astype("int32"), np.floor(y / CELL_M).astype("int32")


def cell_centre_lonlat(cell_x, cell_y):
    x = (np.asarray(cell_x, dtype="float64") + 0.5) * CELL_M
    y = (np.asarray(cell_y, dtype="float64") + 0.5) * CELL_M
    return _FROM_EA.transform(x, y)


def modis_conf_class(v: pd.Series) -> pd.Series:
    """MODIS confidence classes used by the MODIS fire product: <30 low, 30-79 nominal, >=80 high."""
    n = pd.to_numeric(v, errors="coerce")
    out = pd.Series(np.where(n < 30, "low", np.where(n < 80, "nominal", "high")), index=v.index)
    return out.where(n.notna(), "unknown")


def parse_frame(df: pd.DataFrame, source_file: str, processing: str) -> pd.DataFrame:
    """Convert one raw FIRMS table (any known layout) to the common schema."""
    cols = set(df.columns)
    if "brightness" in cols:
        instrument, b1, b2 = "MODIS", "brightness", "bright_t31"
    elif "bright_ti4" in cols:
        instrument, b1, b2 = "VIIRS", "bright_ti4", "bright_ti5"
    else:
        raise ValueError(f"unknown FIRMS layout in {source_file}: {sorted(cols)}")
    out = pd.DataFrame(index=df.index)
    out["lat"] = pd.to_numeric(df["latitude"]).astype("float64")
    out["lon"] = pd.to_numeric(df["longitude"]).astype("float64")
    hhmm = df["acq_time"].astype(str).str.replace(r"\D", "", regex=True).str.zfill(4)
    out["acq_hhmm"] = hhmm
    out["ts_utc"] = pd.to_datetime(df["acq_date"].astype(str) + " " + hhmm, format="%Y-%m-%d %H%M", utc=True)
    out["date"] = out["ts_utc"].dt.tz_localize(None).dt.normalize()
    utc_hour = out["ts_utc"].dt.hour + out["ts_utc"].dt.minute / 60.0
    out["local_solar_hour"] = ((utc_hour + out["lon"] / 15.0) % 24).astype("float32")
    sat = df["satellite"].astype(str).str.strip()
    out["platform"] = sat.map(PLATFORM_MAP)
    if out["platform"].isna().any():
        raise ValueError(f"unknown satellite codes in {source_file}: {sorted(sat[out['platform'].isna()].unique())}")
    out["instrument"] = instrument
    out["processing"] = processing
    out["version"] = df["version"].astype(str)
    out["brightness"] = pd.to_numeric(df[b1], errors="coerce").astype("float32")
    out["brightness_2"] = pd.to_numeric(df[b2], errors="coerce").astype("float32")
    out["frp"] = pd.to_numeric(df["frp"], errors="coerce").astype("float32")
    conf = df["confidence"].astype(str).str.strip()
    out["conf_raw"] = conf
    if instrument == "MODIS":
        out["conf_class"] = modis_conf_class(conf)
    else:
        out["conf_class"] = conf.str.lower().map(VIIRS_CONF).fillna("unknown")
    out["scan_km"] = pd.to_numeric(df["scan"], errors="coerce").astype("float32")
    out["track_km"] = pd.to_numeric(df["track"], errors="coerce").astype("float32")
    out["daynight"] = df["daynight"].astype(str).str.strip()
    if "type" in cols:
        out["det_type"] = pd.to_numeric(df["type"], errors="coerce").astype("Int8")
    else:
        out["det_type"] = pd.array([pd.NA] * len(df), dtype="Int8")
    out["source_file"] = source_file
    out["source_row"] = np.arange(2, len(df) + 2, dtype="int32")  # 1-based line number in the raw file
    return out


def raw_files() -> list[tuple[Path, str]]:
    """All verified raw FIRMS files with their processing level, from the manifest."""
    m = json.loads((config.METADATA / "manifest.json").read_text(encoding="utf-8"))
    out = []
    for rel, e in sorted(m.items()):
        if e.get("status") != "Verified" or e.get("product") == "boundary" or not e.get("rows"):
            continue
        out.append((config.ROOT / rel, e["processing"]))
    return out


def load_admin(level: str, iso3: str = "PAK"):
    gj = json.loads((config.BOUNDARIES / f"geoBoundaries-{iso3}-{level}.geojson").read_text(encoding="utf-8"))
    geoms = [shapely.geometry.shape(f["geometry"]) for f in gj["features"]]
    props = [f["properties"] for f in gj["features"]]
    return geoms, props


def assign_polygons(lon: np.ndarray, lat: np.ndarray, geoms) -> np.ndarray:
    """Index of the polygon containing each point, -1 if none."""
    out = np.full(len(lon), -1, dtype="int16")
    geoms = np.asarray(geoms, dtype=object)
    shapely.prepare(geoms)
    for gi in range(len(geoms) - 1, -1, -1):  # reverse so the first polygon wins on shared borders
        x0, y0, x1, y1 = geoms[gi].bounds
        idx = np.flatnonzero((lon >= x0) & (lon <= x1) & (lat >= y0) & (lat <= y1))
        if len(idx):
            hit = shapely.contains_xy(geoms[gi], lon[idx], lat[idx])
            out[idx[hit]] = gi
    return out


def polygon_area_km2(geom) -> float:
    ea = shapely.transform(geom, lambda c: np.column_stack(_TO_EA.transform(c[:, 0], c[:, 1])))
    return float(ea.area / 1e6)


def build(iso3: str = "PAK") -> dict:
    """Read every verified raw file, normalize, grid, assign regions and write Parquet."""
    frames, report = [], {"files": 0, "raw_rows": 0}
    for path, processing in raw_files():
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        frames.append(parse_frame(df, path.relative_to(config.ROOT).as_posix(), processing))
        report["files"] += 1
        report["raw_rows"] += len(df)
    d = pd.concat(frames, ignore_index=True)
    del frames

    # Regions. ADM0 decides membership of the country AOI.
    g0, _ = load_admin("ADM0", iso3)
    g1, p1 = load_admin("ADM1", iso3)
    g2, p2 = load_admin("ADM2", iso3)
    lon, lat = d["lon"].to_numpy(), d["lat"].to_numpy()
    d["adm1"] = assign_polygons(lon, lat, g1)
    d["in_country"] = d["adm1"] >= 0  # country AOI = union of the ADM1 units
    d["adm2"] = assign_polygons(lon, lat, g2)
    report["outside_country"] = int((~d["in_country"]).sum())
    report["outside_by_processing"] = d.loc[~d["in_country"]].groupby("processing").size().to_dict()

    # Standard data replaces NRT for the same platform and date (never mix both).
    sp_max = d[d["processing"] == "SP"].groupby("platform")["date"].max()
    nrt = d["processing"] == "NRT"
    superseded = nrt & (d["date"] <= d["platform"].map(sp_max).fillna(pd.Timestamp("1900-01-01")))
    report["nrt_superseded_by_sp"] = int(superseded.sum())
    d = d[~superseded]

    # Exact duplicates (same platform, time and position).
    key = ["platform", "ts_utc", "lat", "lon"]
    dup = d.duplicated(key, keep="first")
    report["exact_duplicates_removed"] = int(dup.sum())
    d = d[~dup]

    report["kept_outside_country"] = int((~d["in_country"]).sum())
    d = d[d["in_country"]].drop(columns=["in_country"]).reset_index(drop=True)

    cx, cy = to_cells(d["lon"].to_numpy(), d["lat"].to_numpy())
    d["cell_x"], d["cell_y"] = cx, cy
    d = d.sort_values(["ts_utc", "platform", "lat", "lon"], kind="stable").reset_index(drop=True)
    d.insert(0, "det_id", np.arange(len(d), dtype="int64"))
    for c in ("platform", "instrument", "processing", "version", "conf_class", "daynight", "source_file"):
        d[c] = d[c].astype("category")

    out = config.PROCESSED / "normalized" / "detections.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    d.to_parquet(out, index=False)

    # AOI registry: country, ADM1, ADM2 with names and areas.
    aois = [{"aoi_id": iso3, "level": "ADM0", "name": "Pakistan", "index": 0,
             "area_km2": sum(polygon_area_km2(g) for g in g1)}]
    for i, (g, p) in enumerate(zip(g1, p1)):
        aois.append({"aoi_id": f"{iso3}-ADM1-{i}", "level": "ADM1", "name": p.get("shapeName"), "index": i,
                     "area_km2": polygon_area_km2(g)})
    for i, (g, p) in enumerate(zip(g2, p2)):
        aois.append({"aoi_id": f"{iso3}-ADM2-{i}", "level": "ADM2", "name": p.get("shapeName"), "index": i,
                     "area_km2": polygon_area_km2(g),
                     "adm1": int(assign_polygons(np.array([g.representative_point().x]),
                                                 np.array([g.representative_point().y]), g1)[0])})
    pd.DataFrame(aois).to_parquet(config.PROCESSED / "normalized" / "aois.parquet", index=False)

    report["rows_written"] = len(d)
    report["by_platform_processing"] = {f"{a}/{b}": int(n) for (a, b), n in
                                         d.groupby(["platform", "processing"], observed=True).size().items()}
    report["date_min"], report["date_max"] = str(d["date"].min().date()), str(d["date"].max().date())
    report["null_timestamps"] = int(d["ts_utc"].isna().sum())
    report["no_adm1"] = int((d["adm1"] < 0).sum())
    report["no_adm2"] = int((d["adm2"] < 0).sum())
    (config.PROCESSED / "normalized" / "normalize_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report
