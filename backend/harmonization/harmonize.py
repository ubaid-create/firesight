"""Build the continuous reference-scale (VIIRS S-NPP-equivalent) burning-activity record.

For every AOI and day:
  * per-platform observed active cells (never summed across platforms);
  * 8-day rolling harmonized activity with an 80 % interval (native calibration resolution);
  * a daily value: observed for the reference platform, otherwise the calibrated 8-day total
    distributed over its days in proportion to what the carrier platform observed each day;
  * the carrier platform and method, a provisional flag, percentile indices, anomaly scores.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from backend import config
from backend.analytics.anomaly import seasonal_anomaly
from backend.analytics.critical_windows import critical_windows
from backend.harmonization import calibration as cal

HARM = config.PROCESSED / "harmonized"
PLATFORMS = ["Terra", "Aqua", "MODIS", "SNPP", "NOAA20", "NOAA21", "ALL"]
WINDOW = 8
MIN_ACTIVE_DAYS_FOR_INDEX = 100
MIN_CELL_DAYS_FOR_FLAG = 5  # harmonized cell-days in the 8-day window needed for an anomaly flag
# Maximum acceptable held-out total bias for a carrier link to enter the harmonized record.
MAX_TEST_BIAS_PCT = 10.0


def percentile_index(v: np.ndarray) -> np.ndarray:
    """0 for no activity; otherwise percentile rank (1..100) among the AOI's active days."""
    out = np.full(len(v), np.nan)
    pos = v > 0
    if pos.sum() < MIN_ACTIVE_DAYS_FOR_INDEX:
        return out
    out[v == 0] = 0
    out[pos] = np.ceil(100 * rankdata(v[pos], method="average") / pos.sum())
    return out


def carrier_plan(avail: dict, links: dict) -> dict:
    """Decide which platform carries the record in each period, from real data ranges."""
    fitted = {n: l for n, l in links.items() if l["status"] == "fitted"}

    def usable(name):
        l = fitted.get(name)
        if not l:
            return False, "not fitted"
        b = l["test_scores"][l["chosen_model"]]["total_bias_pct"]
        return (abs(b) <= MAX_TEST_BIAS_PCT), f"held-out total bias {b:+.1f}%"

    plan = {"aqua_start": avail["Aqua"][0], "snpp_start": avail["SNPP"][0] + pd.Timedelta(days=WINDOW - 1),
            "snpp_end": avail["SNPP"][1], "post": None, "notes": {}}
    for name, plat in (("NOAA21_to_SNPP", "NOAA21"), ("NOAA20_to_SNPP", "NOAA20")):
        ok, why = usable(name)
        plan["notes"][name] = why
        if ok and plan["post"] is None and plat in avail and avail[plat][1] > avail["SNPP"][1]:
            plan["post"] = (name, plat)
    return plan


def build_aoi(aoi_id: str, region_id: str, p: pd.DataFrame, dates: pd.DatetimeIndex, avail: dict,
              links: dict, plan: dict, regional: dict | None = None, area_frac: float = 1.0,
              mode: str = "direct"):
    """Harmonized series for one AOI.

    mode "direct": the AOI is a calibration region (province); the fitted model is applied to it.
    mode "scaled": the AOI lies inside a region; the region's calibrated 8-day estimate is shared
                   out in proportion to the carrier platform's cells in the AOI (area share when the
                   carrier saw nothing in the whole region). Sub-areas therefore add up to the region.
    mode "sum":    the AOI is the union of regions; ``regional`` already holds the summed estimates.
    """
    piv = p.pivot(index="date", columns="platform", values="cells")
    nrt = p.pivot(index="date", columns="platform", values="has_nrt")
    out = pd.DataFrame(index=dates)
    month = dates.month.to_numpy()
    cells, roll = {}, {}
    for pl in PLATFORMS:
        v = (piv[pl] if pl in piv.columns else pd.Series(dtype=float)).reindex(dates).fillna(0.0)
        if pl in avail:
            v[(dates < avail[pl][0]) | (dates > avail[pl][1])] = np.nan  # platform not delivering data
        else:
            v[:] = np.nan
        cells[pl] = v
        roll[pl] = v.rolling(WINDOW, min_periods=WINDOW).sum()
        out[f"cells_{pl}"] = v.astype("float32")

    # Fixed 8-day windows aligned to 1 January, as used for calibration (46 per year).
    wid = dates.year.to_numpy() * 100 + (dates.day_of_year.to_numpy() - 1) // WINDOW
    wmonth = pd.Series(month).groupby(wid).transform(lambda s: s.iloc[len(s) // 2]).to_numpy()
    est = {}
    for name, l in links.items():
        if l["status"] != "fitted" or l["y"] != cal.REFERENCE:
            continue
        x = roll[l["x"]].to_numpy()
        ok = ~np.isnan(x)
        tot = np.full(len(x), np.nan)
        lo = np.full(len(x), np.nan)
        hi = np.full(len(x), np.nan)
        if mode == "direct":
            tot[ok] = cal.predict(l["params"], x[ok], month[ok], region_id)
            lo[ok], hi[ok] = cal.interval(tot[ok], l["residual_quantiles"])
        elif mode == "sum":
            tot, lo, hi = (regional[name][k].copy() for k in ("tot", "lo", "hi"))
        else:
            r = regional[name]
            with np.errstate(divide="ignore", invalid="ignore"):
                frac = np.where(r["x"] > 0, x / r["x"], area_frac)
            tot, lo, hi = r["tot"] * frac, r["lo"] * frac, r["hi"] * frac
        xd = cells[l["x"]].to_numpy()
        # Daily values: split the calibrated total of the fixed, calendar-aligned 8-day window that
        # contains the day (the same windows the model was fitted on) in proportion to the carrier's
        # daily cells. Window totals are therefore preserved exactly.
        xs = pd.Series(xd)
        xw = xs.groupby(wid).transform(lambda s: s.sum() if s.notna().all() else np.nan).to_numpy()
        nw = xs.groupby(wid).transform("size").to_numpy().astype(float)
        if mode == "direct":
            tw = np.full(len(x), np.nan)
            okw = ~np.isnan(xw)
            tw[okw] = cal.predict(l["params"], xw[okw], wmonth[okw], region_id)
            lw, hw = np.full(len(x), np.nan), np.full(len(x), np.nan)
            lw[okw], hw[okw] = cal.interval(tw[okw], l["residual_quantiles"])
            with np.errstate(divide="ignore", invalid="ignore"):
                sh = np.where(xw > 0, xd / xw, 1.0 / nw)
            daily, dlo, dhi = tw * sh, lw * sh, hw * sh
        elif mode == "sum":
            r = regional[name]
            tw, lw, hw = r["tw"], r["lw"], r["hw"]
            daily, dlo, dhi = r["daily"].copy(), r["dlo"].copy(), r["dhi"].copy()
        else:
            r = regional[name]
            tw, lw, hw = r["tw"], r["lw"], r["hw"]
            with np.errstate(divide="ignore", invalid="ignore"):
                sh = np.where(r["xw"] > 0, xd / r["xw"], area_frac / nw)
            daily, dlo, dhi = tw * sh, lw * sh, hw * sh
        est[name] = {"roll": tot / WINDOW, "lo": lo / WINDOW, "hi": hi / WINDOW,
                     "daily": daily, "dlo": dlo, "dhi": dhi,
                     "tot": tot, "tlo": lo, "thi": hi, "x": x, "xd": xd,
                     "tw": tw, "lw": lw, "hw": hw, "xw": xw}
    for name, col in (("MODIS_to_SNPP", "eq_modis_roll"), ("NOAA20_to_SNPP", "eq_noaa20_roll"),
                      ("NOAA21_to_SNPP", "eq_noaa21_roll")):
        out[col] = est[name]["roll"].astype("float32") if name in est else np.float32("nan")
    out["eq_modis_daily"] = est["MODIS_to_SNPP"]["daily"].astype("float32") if "MODIS_to_SNPP" in est else np.float32("nan")
    for name, col in (("MODIS_to_SNPP", "eq_modis"), ("NOAA20_to_SNPP", "eq_noaa20"), ("NOAA21_to_SNPP", "eq_noaa21")):
        out[f"{col}_lo"] = est[name]["lo"].astype("float32") if name in est else np.float32("nan")
        out[f"{col}_hi"] = est[name]["hi"].astype("float32") if name in est else np.float32("nan")
    snpp_roll = (roll["SNPP"] / WINDOW).to_numpy()
    out["snpp_roll"] = snpp_roll.astype("float32")
    out["naive_roll"] = (roll["ALL"] / WINDOW).to_numpy().astype("float32")

    n = len(dates)
    h = {k: np.full(n, np.nan) for k in ("roll", "lo", "hi", "daily", "dlo", "dhi", "x", "xd")}
    carrier = np.full(n, "none", dtype=object)
    method = np.full(n, "no_source", dtype=object)

    def use(mask, name, plat, label):
        if name not in est:
            return
        for k in h:
            h[k][mask] = est[name][k][mask]
        carrier[mask] = plat
        method[mask] = label

    d = dates
    use(np.asarray(d < plan["aqua_start"]), "Terra_to_SNPP", "Terra", "calibrated_terra")
    use(np.asarray((d >= plan["aqua_start"]) & (d < plan["snpp_start"])), "MODIS_to_SNPP", "MODIS", "calibrated_modis")
    ref = np.asarray((d >= plan["snpp_start"]) & (d <= plan["snpp_end"]))
    sd = cells["SNPP"].to_numpy()
    h["roll"][ref] = h["lo"][ref] = h["hi"][ref] = snpp_roll[ref]
    h["daily"][ref] = h["dlo"][ref] = h["dhi"][ref] = sd[ref]
    h["x"][ref], h["xd"][ref] = roll["SNPP"].to_numpy()[ref], sd[ref]
    carrier[ref], method[ref] = "SNPP", "reference_observed"
    post = np.asarray(d > plan["snpp_end"])
    if plan["post"] is not None and post.any():
        name, plat = plan["post"]
        use(post, name, plat, f"calibrated_{plat.lower()}")
    method[np.isnan(h["roll"])] = "no_source"
    carrier[np.isnan(h["roll"])] = "none"

    out["h_roll"], out["h_roll_lo"], out["h_roll_hi"] = (h[k].astype("float32") for k in ("roll", "lo", "hi"))
    out["h_daily"], out["h_daily_lo"], out["h_daily_hi"] = (h[k].astype("float32") for k in ("daily", "dlo", "dhi"))
    out["carrier"], out["method"] = carrier, method

    # Provisional when the carrier used near-real-time data anywhere in the 8-day window.
    prov = np.zeros(n, dtype=bool)
    for pl in set(carrier) - {"none"}:
        members = ["Terra", "Aqua"] if pl == "MODIS" else [pl]
        flag = sum((nrt[m] if m in nrt.columns else pd.Series(dtype=float)).reindex(dates).fillna(0).astype(float)
                   for m in members)
        flag = (flag.rolling(WINDOW, min_periods=1).max() > 0).to_numpy()
        prov |= flag & (carrier == pl)
    out["provisional"] = prov

    # Index 0 means "the carrier platform recorded no detections" (in the 8-day window / on the day),
    # not "no fire". Otherwise the percentile rank among this AOI's periods with detections.
    out["carrier_cells_8d"] = h["x"].astype("float32")
    out["index_roll"] = percentile_index(np.where(np.isnan(h["roll"]), -1.0, np.where(h["x"] > 0, h["roll"], 0.0))).astype("float32")
    out["index_daily"] = percentile_index(np.where(np.isnan(h["daily"]), -1.0, np.where(h["xd"] > 0, h["daily"], 0.0))).astype("float32")
    out.loc[np.isnan(h["roll"]), ["index_roll", "index_daily"]] = np.nan
    an = seasonal_anomaly(dates, h["roll"])
    # A statistical flag on almost no activity is noise: require a minimum amount of activity
    # in the 8-day window before calling a period elevated or highly unusual.
    tiny = (np.nan_to_num(h["roll"]) * WINDOW < MIN_CELL_DAYS_FOR_FLAG) & an["anomaly"].isin(["elevated", "highly_unusual"]).to_numpy()
    an.loc[tiny, "anomaly"] = "normal"
    an.loc[tiny, "anomaly_method"] = "below_min_activity"
    for c in an.columns:
        out[c] = an[c].to_numpy()
    out.insert(0, "aoi_id", aoi_id)
    out.insert(1, "date", dates)
    reg = {name: {"tot": e["tot"], "lo": e["tlo"], "hi": e["thi"], "x": e["x"], "tw": e["tw"], "lw": e["lw"],
                  "hw": e["hw"], "xw": e["xw"], "daily": e["daily"], "dlo": e["dlo"], "dhi": e["dhi"]}
           for name, e in est.items()}
    return out.reset_index(drop=True), reg


def build() -> dict:
    pdaily = pd.read_parquet(HARM / "platform_daily.parquet")
    aois = pd.read_parquet(config.PROCESSED / "normalized" / "aois.parquet")
    cinfo = cal.load()
    links = cinfo["links"]
    country = aois.loc[aois["level"] == "ADM0", "aoi_id"].iloc[0]
    c0 = pdaily[pdaily["aoi_id"] == country]
    avail = {p: (s["date"].min(), s["date"].max()) for p, s in c0.groupby("platform")}
    plan = carrier_plan(avail, links)
    dates = pd.date_range(c0["date"].min(), c0["date"].max(), freq="D")
    by_aoi = dict(tuple(pdaily.groupby("aoi_id")))
    frames, windows, wstats = [], [], []
    empty = pdaily.iloc[0:0]
    area = dict(zip(aois["aoi_id"], aois["area_km2"]))

    def finish(aoi_id, f):
        frames.append(f)
        st, wins, info = critical_windows(pd.DatetimeIndex(f["date"]), f["h_daily"].to_numpy())
        for w in wins:
            windows.append({"aoi_id": aoi_id, **w, "threshold": info["threshold"]})
        if len(st):
            wstats.append(st.assign(aoi_id=aoi_id, threshold=info["threshold"]))

    # 1. Calibration regions (ADM1): the fitted models are applied here.
    regional = {}
    for a in aois[aois["level"] == "ADM1"].itertuples():
        f, reg = build_aoi(a.aoi_id, a.aoi_id, by_aoi.get(a.aoi_id, empty), dates, avail, links, plan)
        regional[a.aoi_id] = reg
        finish(a.aoi_id, f)
    # 2. Country: sum of the regional estimates (intervals summed, which is conservative).
    total = {}
    for name in next(iter(regional.values())):
        total[name] = {k: np.sum([regional[r][name][k] for r in regional], axis=0)
                       for k in ("tot", "lo", "hi", "x", "tw", "lw", "hw", "xw", "daily", "dlo", "dhi")}
    f, _ = build_aoi(country, country, by_aoi.get(country, empty), dates, avail, links, plan,
                     regional=total, mode="sum")
    finish(country, f)
    # 3. Districts: share of their province's estimate.
    for a in aois[aois["level"] == "ADM2"].itertuples():
        region = f"{country}-ADM1-{int(a.adm1)}"
        f, _ = build_aoi(a.aoi_id, region, by_aoi.get(a.aoi_id, empty), dates, avail, links, plan,
                         regional=regional[region], area_frac=area[a.aoi_id] / area[region], mode="scaled")
        finish(a.aoi_id, f)
    hd = pd.concat(frames, ignore_index=True)
    for c in ("carrier", "method", "anomaly", "anomaly_method", "aoi_id"):
        hd[c] = hd[c].astype("category")
    hd.to_parquet(HARM / "harmonized_daily.parquet", index=False)
    pd.DataFrame(windows).to_parquet(HARM / "critical_windows.parquet", index=False)
    pd.concat(wstats, ignore_index=True).to_parquet(HARM / "weekly_stats.parquet", index=False)

    c = hd[hd["aoi_id"] == country]
    ref = c[c["method"] == "reference_observed"]
    rep = {
        "aois": int(aois.shape[0]), "rows": int(len(hd)),
        "date_range": [str(dates[0].date()), str(dates[-1].date())],
        "carrier_plan": {"aqua_start": str(plan["aqua_start"].date()), "snpp_reference_from": str(plan["snpp_start"].date()),
                         "snpp_end": str(plan["snpp_end"].date()),
                         "after_snpp": plan["post"][1] if plan["post"] else None, "link_notes": plan["notes"]},
        "country_days_by_method": c["method"].value_counts().to_dict(),
        "country_provisional_days": int(c["provisional"].sum()),
        "check_reference_equals_observed_snpp": bool(np.allclose(ref["h_daily"], ref["cells_SNPP"], equal_nan=True)),
        "check_no_negative": bool((hd[["h_roll", "h_daily"]].min(skipna=True) >= 0).all()),
        "country_anomaly_labels": c["anomaly"].value_counts().to_dict(),
        "aois_with_index": int(hd.groupby("aoi_id", observed=True)["index_roll"].apply(lambda s: s.notna().any()).sum()),
        "aois_with_critical_windows": int(len({w["aoi_id"] for w in windows})),
        "country_critical_windows": [w for w in windows if w["aoi_id"] == country],
    }
    (HARM / "harmonize_report.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    return rep
