"""Historical critical burning windows: weeks of the year that are repeatedly high-activity."""
from __future__ import annotations

import numpy as np
import pandas as pd

from backend.analytics.anomaly import doy365

HIGH_PCTL = 75        # a week is "elevated" in a year when it exceeds this percentile of all active weeks
MIN_SHARE = 0.5       # a week is critical when elevated in at least this share of years
MIN_YEARS = 8


def weekly_table(dates: pd.DatetimeIndex, values: np.ndarray) -> pd.DataFrame:
    """Year x week (1..52) sums on the 365-day calendar; only complete years are returned."""
    v = pd.Series(np.asarray(values, float), index=dates)
    week = np.minimum(doy365(dates) // 7, 51) + 1
    t = pd.DataFrame({"year": dates.year, "week": week, "v": v.to_numpy()})
    days = t.groupby("year")["v"].apply(lambda s: s.notna().sum())
    complete = days[days >= 365].index
    return t[t["year"].isin(complete)].pivot_table(index="year", columns="week", values="v", aggfunc="sum")


def critical_windows(dates: pd.DatetimeIndex, values: np.ndarray) -> tuple[pd.DataFrame, list[dict], dict]:
    wk = weekly_table(dates, values)
    info = {"years_used": int(len(wk)), "threshold": None}
    if len(wk) < MIN_YEARS or not (wk.to_numpy() > 0).any():
        return pd.DataFrame(), [], {**info, "status": "insufficient_history"}
    active = wk.to_numpy()[wk.to_numpy() > 0]
    thr = float(np.percentile(active, HIGH_PCTL))
    stats = pd.DataFrame({
        "week": wk.columns,
        "years": len(wk),
        "years_elevated": (wk > thr).sum(axis=0).to_numpy(),
        "median": wk.median(axis=0).to_numpy(),
        "p25": wk.quantile(0.25, axis=0).to_numpy(),
        "p75": wk.quantile(0.75, axis=0).to_numpy(),
        "max": wk.max(axis=0).to_numpy(),
    })
    stats["share_elevated"] = stats["years_elevated"] / stats["years"]
    stats["critical"] = stats["share_elevated"] >= MIN_SHARE
    windows, cur = [], None
    for r in stats.itertuples():
        if r.critical:
            if cur is None:
                cur = {"start_week": int(r.week), "end_week": int(r.week), "shares": [r.share_elevated],
                       "years_elevated": [int(r.years_elevated)]}
            else:
                cur["end_week"] = int(r.week)
                cur["shares"].append(r.share_elevated)
                cur["years_elevated"].append(int(r.years_elevated))
        elif cur is not None:
            windows.append(cur)
            cur = None
    if cur is not None:
        windows.append(cur)
    ref = pd.Timestamp("2001-01-01")
    out = []
    for w in windows:
        s = ref + pd.Timedelta(days=(w["start_week"] - 1) * 7)
        e = ref + pd.Timedelta(days=min(w["end_week"] * 7 - 1, 364))
        out.append({"start_week": w["start_week"], "end_week": w["end_week"],
                    "start_label": s.strftime("%d %b"), "end_label": e.strftime("%d %b"),
                    "mean_share_elevated": float(np.mean(w["shares"])),
                    "min_years_elevated": int(min(w["years_elevated"])),
                    "max_years_elevated": int(max(w["years_elevated"])), "years_used": int(len(wk))})
    return stats, out, {**info, "threshold": thr, "status": "ok"}
