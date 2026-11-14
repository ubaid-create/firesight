"""Robust seasonal anomaly scores: Z = (x - median) / (1.4826 * MAD).

Baseline for a date: the same day of year +/- ``half_window`` days in every *other* year.
29 February is treated as day 59 (28 February) so that every year has 365 comparable days.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

Z_ELEVATED = 2.0
Z_HIGH = 3.5      # Iglewicz-Hoaglin cut-off for robust z-scores
Z_LOW = -2.0
MIN_BASELINE_YEARS = 5


def doy365(dates: pd.DatetimeIndex) -> np.ndarray:
    """Day of year on a 365-day calendar (0..364); 29 Feb maps onto 28 Feb."""
    doy = dates.day_of_year.to_numpy().copy()
    leap = dates.is_leap_year
    doy[leap & (doy >= 60)] -= 1
    return doy - 1


def seasonal_anomaly(dates: pd.DatetimeIndex, values: np.ndarray, half_window: int = 7) -> pd.DataFrame:
    v = np.asarray(values, float)
    years = dates.year.to_numpy()
    d = doy365(dates)
    ylist = np.unique(years)
    yi = np.searchsorted(ylist, years)
    # year x day matrix (mean of the two values when 28/29 Feb collide)
    M = np.full((len(ylist), 365), np.nan)
    cnt = np.zeros_like(M)
    ok = ~np.isnan(v)
    np.add.at(cnt, (yi[ok], d[ok]), 1)
    S = np.zeros_like(M)
    np.add.at(S, (yi[ok], d[ok]), v[ok])
    M[cnt > 0] = S[cnt > 0] / cnt[cnt > 0]

    med = np.full(M.shape, np.nan)
    mad = np.full(M.shape, np.nan)
    nyr = np.zeros(M.shape, dtype="int16")
    p95 = np.full(M.shape, np.nan)
    mx = np.full(M.shape, np.nan)
    offs = np.arange(-half_window, half_window + 1)
    for j in range(365):
        block = M[:, (j + offs) % 365]                      # years x window
        for i in range(len(ylist)):
            other = np.delete(block, i, axis=0)
            yrs_with = int((~np.isnan(other)).any(axis=1).sum())
            nyr[i, j] = yrs_with
            if yrs_with < MIN_BASELINE_YEARS:
                continue
            vals = other[~np.isnan(other)]
            m = np.median(vals)
            med[i, j] = m
            mad[i, j] = np.median(np.abs(vals - m))
            p95[i, j] = np.quantile(vals, 0.95)
            mx[i, j] = vals.max()

    b_med, b_mad, b_n = med[yi, d], mad[yi, d], nyr[yi, d]
    b_p95, b_max = p95[yi, d], mx[yi, d]
    with np.errstate(divide="ignore", invalid="ignore"):
        z = (v - b_med) / (1.4826 * b_mad)
    label = np.full(len(v), "normal", dtype=object)
    usable = ~np.isnan(v) & ~np.isnan(b_med)
    has_mad = usable & (b_mad > 0)
    label[has_mad & (z >= Z_ELEVATED)] = "elevated"
    label[has_mad & (z >= Z_HIGH)] = "highly_unusual"
    label[has_mad & (z <= Z_LOW)] = "unusually_low"
    # Zero MAD (baseline almost always the same value, typically zero): fall back to rank.
    zero_mad = usable & ~(b_mad > 0)
    z[zero_mad] = np.nan
    label[zero_mad & (v > b_p95)] = "elevated"
    label[zero_mad & (v > b_max)] = "highly_unusual"
    label[~usable] = "insufficient_baseline"
    method = np.where(has_mad, "robust_z", np.where(zero_mad, "rank_fallback", "none"))
    return pd.DataFrame({"z": z.astype("float32"), "anomaly": label, "anomaly_method": method,
                         "base_median": b_med.astype("float32"), "base_mad": b_mad.astype("float32"),
                         "base_years": b_n}, index=dates)
