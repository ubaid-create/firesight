"""Exploratory data analysis and quality report. Writes docs/EDA_REPORT.md from the processed data."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import config  # noqa: E402

NORM = config.PROCESSED / "normalized"
PLAT = ["Terra", "Aqua", "SNPP", "NOAA20", "NOAA21"]


def table(df: pd.DataFrame, index_name: str = "") -> list[str]:
    cols = [index_name] + [str(c) for c in df.columns]
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for i, r in df.iterrows():
        cells = []
        for v in r:
            if pd.isna(v):
                cells.append("")
            elif isinstance(v, (float, np.floating)):
                cells.append(f"{v:,.2f}" if abs(v) < 1000 else f"{v:,.0f}")
            else:
                cells.append(f"{v:,}" if isinstance(v, (int, np.integer)) else str(v))
        out.append(f"| {i} | " + " | ".join(cells) + " |")
    return out + [""]


def counts(df, index, columns):
    return df.groupby([index, columns], observed=True).size().unstack(columns, fill_value=0)


def main():
    d = pd.read_parquet(NORM / "detections.parquet")
    d["platform"] = pd.Categorical(d["platform"].astype(str), PLAT)
    d["year"] = d["date"].dt.year
    d["month"] = d["date"].dt.month
    nrep = json.loads((NORM / "normalize_report.json").read_text())
    arep = json.loads((config.PROCESSED / "harmonized" / "aggregate_report.json").read_text())
    aois = pd.read_parquet(NORM / "aois.parquet")
    cells = pd.read_parquet(config.PROCESSED / "gridded" / "cell_class.parquet")
    L = ["# FireSight — Exploratory Data Analysis and Quality Report", "",
         f"Generated {pd.Timestamp.now():%Y-%m-%d %H:%M} by `scripts/run_eda.py` from `data/processed/normalized/detections.parquet`.", "",
         "## 1. What was loaded", "",
         f"- Raw files read: {nrep['files']} ({nrep['raw_rows']:,} rows).",
         f"- Rows outside Pakistan (API requests use a bounding box that covers neighbouring countries): {nrep['outside_country']:,}, excluded from the Pakistan tables.",
         f"- Near-real-time rows superseded by standard data for the same platform and date: {nrep['nrt_superseded_by_sp']:,}.",
         f"- Exact duplicates (same platform, time, position): {nrep['exact_duplicates_removed']:,}.",
         f"- Detections kept: {nrep['rows_written']:,}, from {nrep['date_min']} to {nrep['date_max']}. Null timestamps: {nrep['null_timestamps']}.",
         f"- Pakistan area used (sum of {int((aois.level == 'ADM1').sum())} ADM1 units): {aois.loc[aois.level == 'ADM0', 'area_km2'].iloc[0]:,.0f} km².", ""]
    L += ["## 2. Detections by platform and processing level", ""]
    L += table(counts(d, "platform", "processing").fillna(0).astype(int), "Platform")
    rng = d.groupby("platform", observed=True)["date"].agg(["min", "max"])
    rng["min"], rng["max"] = rng["min"].dt.date, rng["max"].dt.date
    L += table(rng.rename(columns={"min": "First detection in Pakistan", "max": "Last detection"}), "Platform")
    L += ["## 3. Detections per year", ""]
    L += table(counts(d, "year", "platform").fillna(0).astype(int), "Year")
    L += ["## 4. Seasonal distribution (share of each platform's detections by month, %)", ""]
    m = counts(d, "month", "platform").fillna(0)
    L += table((100 * m / m.sum()).round(1), "Month")
    L += ["## 5. Detection type (standard data only; near-real-time data carry no type)", "",
          "0 = presumed vegetation fire, 1 = active volcano, 2 = other static land source, 3 = offshore.", ""]
    t = counts(d.assign(det_type=d["det_type"].astype("float").fillna(-1).astype(int)), "det_type", "platform").fillna(0).astype(int)
    t.index = ["untyped (NRT)" if i == -1 else str(i) for i in t.index]
    L += table(t, "Type")
    L += ["## 6. Confidence (sensor-specific; the two scales are not equivalent)", "",
          "MODIS: numeric 0–100, classed here as low < 30, nominal 30–79, high ≥ 80. VIIRS: delivered as low / nominal / high.", ""]
    c = counts(d, "conf_class", "platform").fillna(0)
    L += table((100 * c / c.sum()).round(1), "Class (% of platform)")
    mod = d[d["instrument"] == "MODIS"]
    q = pd.to_numeric(mod["conf_raw"], errors="coerce").quantile([0.05, 0.25, 0.5, 0.75, 0.95]).round(0)
    L += ["MODIS raw confidence percentiles (5/25/50/75/95): " + ", ".join(str(int(v)) for v in q), ""]
    L += [f"Default analysis filter (type 0 or untyped, nominal or high confidence) keeps {arep['default_filter_rows']:,} of {arep['detections']:,} detections.", ""]
    L += ["## 7. Product versions", ""]
    L += table(counts(d, "version", "platform").fillna(0).astype(int), "Version")
    L += ["## 8. Overpass time: median local solar time of daytime detections", "",
          "Local solar time = UTC + longitude / 15 hours. A change over the years indicates orbit drift, which changes what part of the daily fire cycle a satellite sees.", ""]
    day = d[d["daynight"] == "D"]
    L += table(day.pivot_table(index="year", columns="platform", values="local_solar_hour", aggfunc="median", observed=False).round(2), "Year")
    L += ["Night-time detections, median local solar time (hours):", ""]
    ngt = d[d["daynight"] == "N"].copy()
    ngt["lst"] = np.where(ngt["local_solar_hour"] > 12, ngt["local_solar_hour"] - 24, ngt["local_solar_hour"])
    L += table(ngt.groupby("platform", observed=True)["lst"].agg(["median", "size"]).round(2), "Platform")
    L += ["## 9. Day / night split and pixel size", ""]
    dn = counts(d, "platform", "daynight").fillna(0)
    dn["night share %"] = (100 * dn.get("N", 0) / dn.sum(axis=1)).round(1)
    L += table(dn, "Platform")
    sc = d.groupby("platform", observed=False)["scan_km"].quantile([0.5, 0.9, 0.99]).unstack().round(2)
    sc.columns = ["scan median km", "scan 90th pct km", "scan 99th pct km"]
    L += table(sc, "Platform")
    L += ["## 10. Fire radiative power (MW per detection, default filter not applied)", ""]
    fr = d.groupby("platform", observed=False)["frp"].quantile([0.5, 0.9, 0.99]).unstack().round(1)
    fr.columns = ["median", "90th pct", "99th pct"]
    L += table(fr, "Platform")
    L += ["FRP is not comparable across MODIS and VIIRS pixels and is never summed across sensors.", ""]
    L += ["## 11. Overpasses with detections per day", "",
          "Distinct acquisition times per platform-day (Pakistan). Hotspot files only list overpasses that produced detections, so this is a lower bound on observation opportunity.", ""]
    ov = d.groupby(["platform", "date"], observed=True)["acq_hhmm"].nunique().groupby("platform", observed=True).agg(["mean", "max"]).round(2)
    L += table(ov, "Platform")
    L += ["## 12. Regions", ""]
    a1 = aois[aois.level == "ADM1"].set_index("index")
    reg = counts(d, "adm1", "platform").fillna(0).astype(int)
    reg.index = [a1.loc[i, "name"] for i in reg.index]
    reg.insert(0, "area km²", [round(a1.set_index("name").loc[n, "area_km2"]) for n in reg.index])
    L += table(reg, "Province / territory")
    L += ["## 13. Persistent thermal sources (1 km cells)", ""]
    pc = cells["persist_class"].value_counts()
    L += [f"- Cells with any detection: {len(cells):,}.",
          f"- Known static (FIRMS type 1, 2 or 3 in at least half of the typed detections): {int(pc.get('known_static', 0)):,}.",
          f"- Suspected persistent (active in ≥ 8 years and ≥ 10 calendar months, busiest month ≤ 25% of active days): {int(pc.get('suspected_persistent', 0)):,}.",
          f"- Normal / seasonal: {int(pc.get('normal', 0)):,}.",
          f"- Untyped near-real-time rows: {arep.get('untyped_rows', 0):,}; of these {arep.get('untyped_rows_in_known_static_cells_excluded_from_default', 0):,} fall in known static cells and are left out of the default view (kept in the data).", ""]
    top = cells[cells.persist_class == "suspected_persistent"].nlargest(10, "active_days")[["cell_x", "cell_y", "active_days", "years_active", "months_active", "max_month_share"]]
    if len(top):
        from backend.processing.normalizer import cell_centre_lonlat
        lon, lat = cell_centre_lonlat(top["cell_x"], top["cell_y"])
        top = top.assign(lon=np.round(lon, 3), lat=np.round(lat, 3)).drop(columns=["cell_x", "cell_y"]).reset_index(drop=True)
        L += ["Ten most active suspected persistent cells:", ""] + table(top, "#")
    (config.ROOT / "docs" / "EDA_REPORT.md").write_text("\n".join(L), encoding="utf-8")
    print("written docs/EDA_REPORT.md", len(L), "lines")


if __name__ == "__main__":
    main()
