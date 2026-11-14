"""FireSight validation experiments. Every number written here is computed from the data.

Run after the pipeline:  python validation/run_validation.py
Outputs: validation/results.json and docs/VALIDATION_REPORT.md
S-NPP is the chosen reference scale, not ground truth: results describe cross-sensor agreement.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import config  # noqa: E402
from backend.harmonization import calibration as cal  # noqa: E402

HARM = config.PROCESSED / "harmonized"
OUT = config.ROOT / "validation" / "results.json"
REPORT = config.ROOT / "docs" / "VALIDATION_REPORT.md"


def annual(c0: pd.DataFrame, col: str) -> pd.Series:
    return c0.groupby(c0["date"].dt.year)[col].sum(min_count=1)


def exp1_raw(pdaily, country):
    c = pdaily[pdaily["aoi_id"] == country].copy()
    c["year"] = c["date"].dt.year
    c["month"] = c["date"].dt.month
    yr = c.pivot_table(index="year", columns="platform", values="cells", aggfunc="sum").fillna(0)
    det = c.pivot_table(index="year", columns="platform", values="n_det", aggfunc="sum").fillna(0)
    rows = []
    for y in yr.index:
        if yr.loc[y].get("SNPP", 0) > 0 and 2012 < y < 2026:
            rows.append({"year": int(y), "modis_cells": int(yr.loc[y, "MODIS"]), "snpp_cells": int(yr.loc[y, "SNPP"]),
                         "cells_ratio": round(yr.loc[y, "SNPP"] / yr.loc[y, "MODIS"], 2),
                         "modis_detections": int(det.loc[y, "MODIS"]), "snpp_detections": int(det.loc[y, "SNPP"]),
                         "detections_ratio": round(det.loc[y, "SNPP"] / det.loc[y, "MODIS"], 2)})
    m = c[(c["year"] >= 2013) & (c["year"] <= 2025)].pivot_table(index="month", columns="platform", values="cells", aggfunc="sum")
    monthly = [{"month": int(i), "cells_ratio": round(r["SNPP"] / r["MODIS"], 2)} for i, r in m.iterrows()]
    return {"by_year": rows, "by_month_2013_2025": monthly}


def exp2_transitions(hd, country):
    c = hd[hd["aoi_id"] == country].set_index("date")
    series = {"naive_union": c["cells_ALL"], "modis_only": c["cells_MODIS"], "terra_only": c["cells_Terra"],
              "harmonized": c["h_daily"]}

    def step(col, before, after):
        s = series[col]
        b = s[(s.index.year >= before[0]) & (s.index.year <= before[1])].groupby(lambda d: d.year).sum().mean()
        a = s[(s.index.year >= after[0]) & (s.index.year <= after[1])].groupby(lambda d: d.year).sum().mean()
        return float(a / b) if b > 0 else None

    out = {}
    for name, before, after, control in (
            ("Aqua added (2002)", (2001, 2001), (2003, 2005), "terra_only"),
            ("S-NPP added (2012)", (2009, 2011), (2013, 2015), "modis_only"),
            ("NOAA-20 added (2018)", (2015, 2017), (2019, 2021), "modis_only"),
            ("NOAA-21 added (2023)", (2020, 2022), (2024, 2025), "modis_only")):
        ctl = step(control, before, after)
        r = {"before_years": list(before), "after_years": list(after), "control_series": control,
             "control_ratio": ctl}
        for col in ("naive_union", "harmonized"):
            v = step(col, before, after)
            r[f"{col}_ratio"] = v
            r[f"{col}_excess_over_control_pct"] = float(100 * (v / ctl - 1)) if v and ctl else None
        out[name] = r
    ann = pd.DataFrame({k: v.groupby(lambda d: d.year).sum(min_count=1) for k, v in series.items()})
    ann = ann[(ann.index >= 2001) & (ann.index <= 2025)]
    out["annual_cell_days"] = [{"year": int(y), **{k: (None if pd.isna(v) else round(float(v))) for k, v in r.items()}}
                               for y, r in ann.iterrows()]
    return out


def exp3_scales(hd, aois, links):
    """Held-out agreement of calibrated MODIS with observed S-NPP at each spatial scale."""
    l = links["MODIS_to_SNPP"]
    t0, t1 = pd.Timestamp(l["test_period"][0]), pd.Timestamp(l["test_period"][1])
    h = hd[(hd["date"] >= t0 + pd.Timedelta(days=7)) & (hd["date"] <= t1)]
    level = dict(zip(aois["aoi_id"], aois["level"]))
    h = h.assign(level=h["aoi_id"].map(level).astype(str))
    out = {}
    for lev, g in h.groupby("level"):
        # non-overlapping 8-day samples (every 8th day) to avoid counting each window eight times
        s = g[((g["date"] - t0).dt.days % 8) == 7]
        r8 = cal.metrics(s["snpp_roll"] * 8, s["eq_modis_roll"] * 8, s["eq_modis_lo"] * 8, s["eq_modis_hi"] * 8)
        dly = cal.metrics(g["cells_SNPP"], g["eq_modis_daily"])
        out[lev] = {"aois": int(g["aoi_id"].nunique()), "eight_day": r8, "daily": dly}
    return out


def exp6_sensitivity(pdaily, regions, links):
    link = next(l for l in cal.LINKS if l["name"] == "MODIS_to_SNPP")
    model = links["MODIS_to_SNPP"]["chosen_model"]
    out = {}
    for label, col in (("1 km grid (default)", "cells"), ("2 km grid", "cells_2km"),
                       ("near-nadir pixels only", "cells_nadir"), ("including low confidence", "cells_incl_low"),
                       ("excluding suspected persistent sources", "cells_nopersist")):
        w = cal.window_table(pdaily[pdaily["aoi_id"].isin(regions)], col)
        ftr = cal.link_frame(w, link, regions, link["train"])
        fte = cal.link_frame(w, link, regions, link["test"])
        p = cal.fit(model, ftr)
        m = cal.metrics(fte["y"], cal.predict(p, fte["x"], fte["month"], fte["aoi_id"]))
        out[label] = {"train_ratio_snpp_per_modis": round(p["k"], 3), "test_mae": m["mae"], "test_mean_ref": m["mean_ref"],
                      "test_total_bias_pct": m["total_bias_pct"], "test_spearman": m["spearman"], "test_log_mae": m["log_mae"]}
    return out


def exp7_geographic(pdaily, regions, links, aois):
    link = next(l for l in cal.LINKS if l["name"] == "MODIS_to_SNPP")
    model = links["MODIS_to_SNPP"]["chosen_model"]
    w = cal.window_table(pdaily[pdaily["aoi_id"].isin(regions)])
    names = dict(zip(aois["aoi_id"], aois["name"]))
    out = {}
    for held in regions:
        rest = [r for r in regions if r != held]
        p = cal.fit(model, cal.link_frame(w, link, rest, link["train"]))
        fte = cal.link_frame(w, link, [held], link["test"])
        m = cal.metrics(fte["y"], cal.predict(p, fte["x"], fte["month"], fte["aoi_id"]))
        out[names[held]] = {k: m[k] for k in ("n", "n_nonzero_ref", "mean_ref", "mae", "total_bias_pct", "spearman")}
    return out


def exp8_correspondence():
    """Same-day, daytime Aqua vs S-NPP agreement on the 1 km grid (both overpass near 13:30)."""
    cd = pd.read_parquet(config.PROCESSED / "gridded" / "cell_day.parquet",
                         columns=["cell", "date", "platform", "cell_x", "cell_y", "lst_min"])
    cd = cd[(cd["lst_min"] > 9) & (cd["lst_min"] < 18)]
    a = cd[cd["platform"] == "Aqua"]
    s = cd[cd["platform"] == "SNPP"]
    a = a[(a["date"] >= s["date"].min()) & (a["date"] <= s["date"].max())]
    key = lambda d, dx=0, dy=0: (d["date"].astype("int64") // 86_400_000_000_000) * 10_000_000_000 + \
        (d["cell_y"].astype("int64") + dy) * 100_000 + (d["cell_x"].astype("int64") + dx)  # noqa: E731
    s_keys = set(key(s).tolist())
    a_keys = set(key(a).tolist())
    out = {}
    for label, yrs in (("2012-2021", (2012, 2021)), ("2022-2025", (2022, 2025))):
        aa = a[(a["date"].dt.year >= yrs[0]) & (a["date"].dt.year <= yrs[1])]
        ss = s[(s["date"].dt.year >= yrs[0]) & (s["date"].dt.year <= yrs[1])]
        same = np.fromiter((k in s_keys for k in key(aa).tolist()), bool, len(aa))
        near = same.copy()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                near |= np.fromiter((k in s_keys for k in key(aa, dx, dy).tolist()), bool, len(aa))
        s_near = np.zeros(len(ss), bool)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                s_near |= np.fromiter((k in a_keys for k in key(ss, dx, dy).tolist()), bool, len(ss))
        out[label] = {"aqua_cell_days": int(len(aa)), "snpp_cell_days": int(len(ss)),
                      "aqua_cells_with_snpp_same_cell_pct": float(100 * same.mean()),
                      "aqua_cells_with_snpp_within_1_cell_pct": float(100 * near.mean()),
                      "snpp_cells_with_aqua_within_1_cell_pct": float(100 * s_near.mean())}
    return out


def fmt(v, nd=1):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    return f"{v:,.{nd}f}" if isinstance(v, float) else f"{v:,}"


def write_report(res: dict):
    L = ["# FireSight — Validation Report", "",
         f"Generated from the processed data on {pd.Timestamp.now():%Y-%m-%d %H:%M}. Every figure below is computed by `validation/run_validation.py`.",
         "", "VIIRS S-NPP is the chosen reference scale, not ground truth. The figures describe agreement between sensors, not fire-detection accuracy.",
         "Unit: *cell-days* = sum over days of unique active 1 km cells (default filter: vegetation-fire type or untyped, nominal or high confidence).", ""]
    L += ["## 1. Calibration links: held-out results", "",
          "Units are 8-day windows per province (ADM1). The model for each link was chosen by blocked cross-validation inside the training years only; the test years were scored once.", "",
          "| Link | Train | Test | Windows (train / test) | Chosen model | Uncalibrated total bias | Calibrated total bias | MAE | Mean reference | Spearman | 80% interval coverage |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, l in res["links"].items():
        if l["status"] != "fitted":
            L.append(f"| {n} | — | — | — | {l['status']} | — | — | — | — | — | — |")
            continue
        t = l["test_scores"][l["chosen_model"]]
        u = l["test_scores"]["uncalibrated"]
        L.append(f"| {n} | {l['train_period'][0]} – {l['train_period'][1]} | {l['test_period'][0]} – {l['test_period'][1]} | "
                 f"{l['train_windows']:,} / {l['test_windows']:,} | {l['chosen_model']} | {fmt(u['total_bias_pct'])}% | "
                 f"{fmt(t['total_bias_pct'])}% | {fmt(t['mae'])} | {fmt(t['mean_ref'])} | {fmt(t['spearman'], 3)} | {fmt(t['interval_coverage_pct'])}% |")
    L += ["", "### Held-out total bias by year (chosen model)", ""]
    years = sorted({int(y) for l in res["links"].values() if l["status"] == "fitted" for y in l["test_by_year"]})
    L += ["| Link | " + " | ".join(str(y) for y in years) + " |", "|---|" + "---|" * len(years)]
    for n, l in res["links"].items():
        if l["status"] == "fitted":
            L.append(f"| {n} | " + " | ".join(
                (fmt(l["test_by_year"][str(y)]["total_bias_pct"]) + "%") if str(y) in l["test_by_year"] else "" for y in years) + " |")
    L += ["", "### All candidate models (cross-validation in training years, then test)", ""]
    for n, l in res["links"].items():
        if l["status"] != "fitted":
            continue
        L += [f"**{n}**", "", "| Model | CV log-MAE | CV total bias | Test log-MAE | Test MAE | Test total bias | Test Spearman |", "|---|---|---|---|---|---|---|"]
        for m in cal.MODELS:
            c, t = l["cv_scores_training_years"][m], l["test_scores"][m]
            mark = " (chosen)" if m == l["chosen_model"] else ""
            L.append(f"| {m}{mark} | {fmt(c['log_mae'], 3)} | {fmt(c['total_bias_pct'])}% | {fmt(t['log_mae'], 3)} | {fmt(t['mae'])} | {fmt(t['total_bias_pct'])}% | {fmt(t['spearman'], 3)} |")
        L.append("")
    L += ["## 2. Raw MODIS versus raw S-NPP (Pakistan)", "", "| Year | MODIS cell-days | S-NPP cell-days | Ratio | MODIS detections | S-NPP detections | Ratio |", "|---|---|---|---|---|---|---|"]
    for r in res["exp1_raw"]["by_year"]:
        L.append(f"| {r['year']} | {r['modis_cells']:,} | {r['snpp_cells']:,} | {r['cells_ratio']} | {r['modis_detections']:,} | {r['snpp_detections']:,} | {r['detections_ratio']} |")
    L += ["", "S-NPP / MODIS cell-day ratio by calendar month, 2013–2025: " +
          ", ".join(f"{r['month']}: {r['cells_ratio']}" for r in res["exp1_raw"]["by_month_2013_2025"]), ""]
    L += ["## 3. Platform transitions: naive merge versus harmonized record", "",
          "Ratio of mean annual activity after a platform was added to mean annual activity before. The control series is a platform that existed on both sides, so its ratio reflects real change in fire activity. \"Excess\" is how far a series departs from the control.", "",
          "| Transition | Years before → after | Control | Control ratio | Naive merge ratio | Naive excess | Harmonized ratio | Harmonized excess |", "|---|---|---|---|---|---|---|---|"]
    for n, r in res["exp2_transitions"].items():
        if n == "annual_cell_days":
            continue
        L.append(f"| {n} | {r['before_years'][0]}–{r['before_years'][1]} → {r['after_years'][0]}–{r['after_years'][1]} | {r['control_series']} | "
                 f"{fmt(r['control_ratio'], 2)} | {fmt(r['naive_union_ratio'], 2)} | {fmt(r['naive_union_excess_over_control_pct'])}% | "
                 f"{fmt(r['harmonized_ratio'], 2)} | {fmt(r['harmonized_excess_over_control_pct'])}% |")
    L += ["", "The harmonized values before 2012 come from a calibration fitted on 2012–2021, so the 2012 row is not an independent test: no VIIRS data exist before 2012 to test against. The independent evidence is the held-out table in section 1.", ""]
    L += ["## 4. Agreement by spatial scale (calibrated MODIS versus observed S-NPP, test years)", "",
          "| Scale | AOIs | 8-day MAE | 8-day mean reference | 8-day total bias | 8-day Spearman | 8-day interval coverage | Daily MAE | Daily mean reference | Daily Spearman |", "|---|---|---|---|---|---|---|---|---|---|"]
    for lev, r in res["exp3_scales"].items():
        e, d = r["eight_day"], r["daily"]
        L.append(f"| {lev} | {r['aois']} | {fmt(e['mae'])} | {fmt(e['mean_ref'])} | {fmt(e['total_bias_pct'])}% | {fmt(e['spearman'], 3)} | {fmt(e['interval_coverage_pct'])}% | {fmt(d['mae'])} | {fmt(d['mean_ref'])} | {fmt(d['spearman'], 3)} |")
    L += ["", "## 5. Sensitivity of the MODIS → S-NPP link", "", "| Variant | S-NPP per MODIS (training) | Test MAE | Test mean reference | Test total bias | Test Spearman |", "|---|---|---|---|---|---|"]
    for n, r in res["exp6_sensitivity"].items():
        L.append(f"| {n} | {r['train_ratio_snpp_per_modis']} | {fmt(r['test_mae'])} | {fmt(r['test_mean_ref'])} | {fmt(r['test_total_bias_pct'])}% | {fmt(r['test_spearman'], 3)} |")
    L += ["", "## 6. Geographic holdout (MODIS → S-NPP)", "", "Model fitted on the other provinces (training years), scored on the held-out province (test years).", "",
          "| Held-out province | Windows | Windows with S-NPP activity | Mean reference | MAE | Total bias | Spearman |", "|---|---|---|---|---|---|---|"]
    for n, r in res["exp7_geographic"].items():
        L.append(f"| {n} | {r['n']} | {r['n_nonzero_ref']} | {fmt(r['mean_ref'])} | {fmt(r['mae'])} | {fmt(r['total_bias_pct'])}% | {fmt(r['spearman'], 3)} |")
    L += ["", "## 7. Cross-sensor correspondence (Aqua versus S-NPP, daytime, same day)", "",
          "| Period | Aqua cell-days | S-NPP cell-days | Aqua cells with S-NPP in same cell | Aqua cells with S-NPP within one cell | S-NPP cells with Aqua within one cell |", "|---|---|---|---|---|---|"]
    for n, r in res["exp8_correspondence"].items():
        L.append(f"| {n} | {r['aqua_cell_days']:,} | {r['snpp_cell_days']:,} | {fmt(r['aqua_cells_with_snpp_same_cell_pct'])}% | {fmt(r['aqua_cells_with_snpp_within_1_cell_pct'])}% | {fmt(r['snpp_cells_with_aqua_within_1_cell_pct'])}% |")
    L += ["", "A same-day match within one cell is evidence of correspondence, not proof that both sensors saw the same fire.", ""]
    REPORT.write_text("\n".join(L), encoding="utf-8")


def main():
    pdaily = pd.read_parquet(HARM / "platform_daily.parquet")
    hd = pd.read_parquet(HARM / "harmonized_daily.parquet")
    aois = pd.read_parquet(config.PROCESSED / "normalized" / "aois.parquet")
    links = cal.load()["links"]
    country = aois.loc[aois["level"] == "ADM0", "aoi_id"].iloc[0]
    regions = cal.region_ids(pdaily)
    res = {"generated": str(pd.Timestamp.now()), "links": links,
           "exp1_raw": exp1_raw(pdaily, country),
           "exp2_transitions": exp2_transitions(hd, country),
           "exp3_scales": exp3_scales(hd, aois, links),
           "exp6_sensitivity": exp6_sensitivity(pdaily, regions, links),
           "exp7_geographic": exp7_geographic(pdaily, regions, links, aois),
           "exp8_correspondence": exp8_correspondence()}
    res = json.loads(json.dumps(res, default=lambda o: None if isinstance(o, float) and np.isnan(o) else str(o)))
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    write_report(res)
    print("written:", OUT.relative_to(config.ROOT), REPORT.relative_to(config.ROOT))


if __name__ == "__main__":
    main()
