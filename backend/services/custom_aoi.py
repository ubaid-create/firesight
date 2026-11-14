"""Custom AOIs (polygons or bounding boxes).

Inside the preprocessed Pakistan coverage the AOI gets the full treatment: per-platform observed
active cells from the 1 km cell-day table, the Pakistan-fitted calibration applied directly to the
AOI, anomalies and critical windows. Reliability is measured for that AOI on the held-out years and
reported. Outside Pakistan no historical data are held: such AOIs are marked "not acquired" and
only on-demand raw FIRMS observations (recent days) can be shown; Pakistan calibration is never
applied there.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache

import numpy as np
import pandas as pd
import shapely
from scipy.stats import spearmanr

from backend import config
from backend.analytics.critical_windows import critical_windows
from backend.harmonization import calibration as cal
from backend.harmonization import harmonize as hz
from backend.processing.normalizer import cell_centre_lonlat, load_admin, polygon_area_km2

CUSTOM = config.PROCESSED / "custom"
MIN_OVERLAP = 0.95  # share of the AOI that must lie inside Pakistan for the processed record to apply


@lru_cache(maxsize=1)
def context():
    pdaily = pd.read_parquet(config.PROCESSED / "harmonized" / "platform_daily.parquet",
                             filters=[("aoi_id", "==", "PAK")])
    avail = {p: (s["date"].min(), s["date"].max()) for p, s in pdaily.groupby("platform")}
    links = cal.load()["links"]
    plan = hz.carrier_plan(avail, links)
    dates = pd.date_range(pdaily["date"].min(), pdaily["date"].max(), freq="D")
    g0, _ = load_admin("ADM1", "PAK")
    country = shapely.union_all(g0)
    return {"avail": avail, "links": links, "plan": plan, "dates": dates, "country": country}


@lru_cache(maxsize=1)
def cell_day():
    cd = pd.read_parquet(config.PROCESSED / "gridded" / "cell_day.parquet",
                         columns=["cell", "date", "platform", "cell_x", "cell_y", "is_nrt"])
    cd["platform"] = cd["platform"].astype(str)
    cells = cd.drop_duplicates("cell")[["cell", "cell_x", "cell_y"]].copy()
    lon, lat = cell_centre_lonlat(cells["cell_x"].to_numpy(), cells["cell_y"].to_numpy())
    cells["lon"], cells["lat"] = lon, lat
    return cd, cells


def geometry_from(spec: dict):
    """spec: {"type": "bbox", "bbox": [w,s,e,n]} or {"type": "polygon", "coordinates": [[lon,lat], ...]}."""
    if spec["type"] == "bbox":
        w, s, e, n = (float(v) for v in spec["bbox"])
        if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
            raise ValueError("invalid bounding box")
        return shapely.box(w, s, e, n)
    ring = [(float(x), float(y)) for x, y in spec["coordinates"]]
    if len(ring) < 3:
        raise ValueError("a polygon needs at least 3 points")
    g = shapely.Polygon(ring)
    if not g.is_valid:
        g = shapely.make_valid(g)
    if g.is_empty or g.area == 0:
        raise ValueError("empty polygon")
    return g


def aoi_id_for(geom) -> str:
    return "CUSTOM-" + hashlib.sha1(geom.wkb).hexdigest()[:10]


def path_for(aoi_id: str):
    return CUSTOM / f"{aoi_id}.parquet", CUSTOM / f"{aoi_id}.json"


def create(spec: dict, name: str | None = None, fixed_id: str | None = None) -> dict:
    geom = geometry_from(spec)
    aoi_id = fixed_id or aoi_id_for(geom)
    pq, meta_p = path_for(aoi_id)
    if pq.exists() and meta_p.exists():
        return json.loads(meta_p.read_text(encoding="utf-8"))
    ctx = context()
    area = polygon_area_km2(geom)
    inside = geom.intersection(ctx["country"])
    share = polygon_area_km2(inside) / area if area > 0 and not inside.is_empty else 0.0
    w, s, e, n = geom.bounds
    meta = {"aoi_id": aoi_id, "name": name or f"Custom area {aoi_id[-6:]}", "level": "CUSTOM",
            "geometry": shapely.geometry.mapping(geom), "bounds": [w, s, e, n], "area_km2": area,
            "share_inside_pakistan": share}
    CUSTOM.mkdir(parents=True, exist_ok=True)
    if share < MIN_OVERLAP:
        meta.update(coverage="not_acquired", harmonized=False,
                    note="Historical FIRMS data have not been acquired for this area. Only recent raw "
                         "observations can be retrieved on demand; the Pakistan calibration is not applied.")
        meta_p.write_text(json.dumps(meta), encoding="utf-8")
        return meta

    cd, cells = cell_day()
    box = cells[(cells["lon"] >= w) & (cells["lon"] <= e) & (cells["lat"] >= s) & (cells["lat"] <= n)]
    sel = box["cell"][shapely.contains_xy(geom, box["lon"].to_numpy(), box["lat"].to_numpy())]
    sub = cd[cd["cell"].isin(set(sel.tolist()))]
    parts = []
    for plat, members in (("Terra", ["Terra"]), ("Aqua", ["Aqua"]), ("SNPP", ["SNPP"]), ("NOAA20", ["NOAA20"]),
                          ("NOAA21", ["NOAA21"]), ("MODIS", ["Terra", "Aqua"]),
                          ("ALL", ["Terra", "Aqua", "SNPP", "NOAA20", "NOAA21"])):
        q = sub[sub["platform"].isin(members)]
        g = q.groupby(["date", "cell"], observed=True)["is_nrt"].max().reset_index()
        agg = g.groupby("date").agg(cells=("cell", "size"), has_nrt=("is_nrt", "max")).reset_index()
        agg["platform"] = plat
        parts.append(agg)
    p = pd.concat(parts, ignore_index=True)
    p["aoi_id"] = aoi_id
    f, _ = hz.build_aoi(aoi_id, "PAK", p, ctx["dates"], ctx["avail"], ctx["links"], ctx["plan"])
    f.to_parquet(pq, index=False)

    # Held-out agreement for this AOI (calibrated MODIS vs observed S-NPP, 2022-2025, 8-day samples).
    t = f[(f["date"] >= "2022-01-08") & (f["date"] <= "2025-12-31")]
    t = t[((t["date"] - pd.Timestamp("2022-01-08")).dt.days % 8) == 0]
    y, yh = t["snpp_roll"].to_numpy() * 8, t["eq_modis_roll"].to_numpy() * 8
    ok = ~np.isnan(y) & ~np.isnan(yh)
    y, yh = y[ok], yh[ok]
    active = int((y > 0).sum())
    rho = float(spearmanr(y, yh).statistic) if active >= 10 and y.std() > 0 and yh.std() > 0 else None
    rating = "insufficient" if f["index_roll"].isna().all() else (
        "moderate" if (rho or 0) >= 0.8 and active >= 30 else "low" if (rho or 0) >= 0.6 and active >= 30 else "very_low")
    st, wins, info = critical_windows(pd.DatetimeIndex(f["date"]), f["h_daily"].to_numpy())
    meta.update(coverage="pakistan_processed", harmonized=True, cells=int(len(sel)),
                reliability={"rating": rating, "test_spearman": rho, "test_windows_active": active},
                windows=wins, windows_info={k: v for k, v in info.items()},
                weekly=st.to_dict("records") if len(st) else [],
                note="Calibrated with the Pakistan province-fitted models applied directly to this area. "
                     "Reliability is reported for this area from the held-out years.")
    meta_p.write_text(json.dumps(meta, default=float), encoding="utf-8")
    return meta


def load_meta(aoi_id: str) -> dict | None:
    _, meta_p = path_for(aoi_id)
    return json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else None


def load_frame(aoi_id: str) -> pd.DataFrame | None:
    pq, _ = path_for(aoi_id)
    return pd.read_parquet(pq) if pq.exists() else None
