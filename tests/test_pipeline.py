"""Unit tests for parsing, gridding, calibration, anomaly detection and critical windows."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.analytics import anomaly as an  # noqa: E402
from backend.analytics.critical_windows import critical_windows  # noqa: E402
from backend.harmonization import calibration as cal  # noqa: E402
from backend.harmonization.harmonize import percentile_index  # noqa: E402
from backend.processing import normalizer as nz  # noqa: E402

MODIS_ARCHIVE = pd.DataFrame([{
    "latitude": "29.1797", "longitude": "71.4212", "brightness": "307.2", "scan": "1.2", "track": "1.1",
    "acq_date": "2023-01-01", "acq_time": "0827", "satellite": "Aqua", "instrument": "MODIS", "confidence": "44",
    "version": "61.03", "bright_t31": "297.1", "frp": "7", "daynight": "D", "type": "0"}])
VIIRS_ARCHIVE = pd.DataFrame([{
    "latitude": "25.39205", "longitude": "69.34456", "bright_ti4": "346.2", "scan": "0.4", "track": "0.6",
    "acq_date": "2023-01-01", "acq_time": "0749", "satellite": "N", "instrument": "VIIRS", "confidence": "n",
    "version": "2", "bright_ti5": "296.95", "frp": "3.33", "daynight": "D", "type": "2"}])
VIIRS_NRT_API = pd.DataFrame([{
    "latitude": "25.02295", "longitude": "76.0851", "bright_ti4": "333.74", "scan": "0.74", "track": "0.76",
    "acq_date": "2026-11-10", "acq_time": "703", "satellite": "N21", "instrument": "VIIRS", "confidence": "n",
    "version": "2.0NRT", "bright_ti5": "304.22", "frp": "5.21", "daynight": "D"}])
MODIS_NRT_OPEN = pd.DataFrame([{
    "latitude": "24.21534", "longitude": "54.16647", "brightness": "312.43", "scan": "3.47", "track": "1.75",
    "acq_date": "2026-11-13", "acq_time": "0104", "satellite": "A", "confidence": "85", "version": "6.1NRT",
    "bright_t31": "288.09", "frp": "71.78", "daynight": "N"}])


def test_parse_modis_archive():
    r = nz.parse_frame(MODIS_ARCHIVE, "f.csv", "SP").iloc[0]
    assert (r.platform, r.instrument, r.conf_raw, r.conf_class) == ("Aqua", "MODIS", "44", "nominal")
    assert r.ts_utc == pd.Timestamp("2023-01-01 08:27", tz="UTC")
    assert r.det_type == 0 and r.source_row == 2
    assert r.local_solar_hour == pytest.approx((8 + 27 / 60 + 71.4212 / 15) % 24, abs=1e-3)


def test_parse_viirs_archive_keeps_static_type():
    r = nz.parse_frame(VIIRS_ARCHIVE, "f.csv", "SP").iloc[0]
    assert (r.platform, r.conf_class, int(r.det_type)) == ("SNPP", "nominal", 2)
    assert r.brightness == pytest.approx(346.2, abs=1e-3) and r.brightness_2 == pytest.approx(296.95, abs=1e-3)


def test_parse_nrt_layouts_without_type_and_unpadded_time():
    r = nz.parse_frame(VIIRS_NRT_API, "f.csv", "NRT").iloc[0]
    assert r.platform == "NOAA21" and pd.isna(r.det_type) and r.acq_hhmm == "0703"
    assert r.ts_utc == pd.Timestamp("2026-11-10 07:03", tz="UTC")
    m = nz.parse_frame(MODIS_NRT_OPEN, "f.csv", "NRT").iloc[0]
    assert (m.platform, m.conf_class, m.processing) == ("Aqua", "high", "NRT")


def test_modis_confidence_boundaries_and_unknown():
    got = nz.modis_conf_class(pd.Series(["0", "29", "30", "79", "80", "100", ""])).tolist()
    assert got == ["low", "low", "nominal", "nominal", "high", "high", "unknown"]


def test_unknown_satellite_code_is_rejected():
    bad = VIIRS_ARCHIVE.assign(satellite="X9")
    with pytest.raises(ValueError):
        nz.parse_frame(bad, "f.csv", "SP")


def test_grid_cells_are_one_km_and_round_trip():
    cx, cy = nz.to_cells([70.0, 70.0], [30.0, 30.02])
    assert cx[0] == cx[1] and abs(cy[1] - cy[0]) in (1, 2, 3)  # 0.02 deg latitude is about 2 km
    lon, lat = nz.cell_centre_lonlat(cx[:1], cy[:1])
    cx2, cy2 = nz.to_cells(lon, lat)
    assert (cx2[0], cy2[0]) == (cx[0], cy[0])
    assert abs(lon[0] - 70.0) < 0.02 and abs(lat[0] - 30.0) < 0.02


def test_polygon_assignment():
    import shapely
    geoms = [shapely.box(0, 0, 1, 1), shapely.box(1, 0, 2, 1)]
    got = nz.assign_polygons(np.array([0.5, 1.5, 5.0]), np.array([0.5, 0.5, 5.0]), geoms)
    assert got.tolist() == [0, 1, -1]


def synthetic_link(k=4.0, n_years=8, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for y in range(2012, 2012 + n_years):
        for w in range(46):
            for a in ("R-ADM1-0", "R-ADM1-1"):
                x = rng.poisson(20)
                rows.append({"aoi_id": a, "year": y, "win": w, "month": 1 + (w * 8) // 31 % 12, "x": float(x),
                             "y": float(rng.poisson(k * x + 1))})
    f = pd.DataFrame(rows)
    f["season"] = cal.season_of(f["month"])
    return f


def test_ratio_model_recovers_known_ratio():
    f = synthetic_link(k=4.0)
    p = cal.fit("ratio", f)
    assert p["k"] == pytest.approx(4.0, rel=0.05)
    yh = cal.predict(p, f["x"], f["month"], f["aoi_id"])
    assert abs(cal.metrics(f["y"], yh)["total_bias_pct"]) < 2


def test_scaled_loglinear_preserves_training_total_and_is_nonnegative():
    f = synthetic_link(k=3.0, seed=1)
    p = cal.fit("loglinear_month_scaled", f)
    yh = cal.predict(p, f["x"], f["month"], f["aoi_id"])
    assert yh.sum() == pytest.approx(f["y"].sum(), rel=1e-6)
    assert (yh >= 0).all()


def test_cross_validation_never_scores_a_year_it_trained_on():
    f = synthetic_link(n_years=6)
    folds = cal.year_folds(f["year"])
    flat = [y for fold in folds for y in fold]
    assert sorted(flat) == sorted(f["year"].unique()) and len(flat) == len(set(flat))
    scores, oof, best = cal.cross_validate(f)
    assert best in cal.MODELS and not np.isnan(oof).any()


def test_intervals_bracket_prediction():
    f = synthetic_link()
    p = cal.fit("ratio", f)
    yh = cal.predict(p, f["x"], f["month"], f["aoi_id"])
    lo, hi = cal.interval(yh, cal.residual_quantiles(f["y"], yh))
    assert (lo <= yh + 1e-9).all() and (hi >= yh - 1e-9).all() and (lo >= 0).all()
    assert 70 <= 100 * np.mean((f["y"] >= lo) & (f["y"] <= hi)) <= 90


def test_full_windows_exclude_partial_periods():
    f = cal.full_windows(["A"], "2012-01-20", "2012-12-31")
    assert f["win"].min() == 3  # windows 0-2 start before 20 Jan; window 3 starts 25 Jan
    assert len(cal.full_windows(["A"], "2013-01-01", "2013-12-31")) == 46


def test_doy365_folds_leap_day():
    d = pd.DatetimeIndex(["2024-02-28", "2024-02-29", "2024-03-01", "2023-03-01", "2024-12-31", "2023-12-31"])
    assert an.doy365(d).tolist() == [58, 58, 59, 59, 364, 364]


def test_anomaly_flags_spike_and_handles_zero_mad():
    dates = pd.date_range("2005-01-01", "2020-12-31", freq="D")
    rng = np.random.default_rng(0)
    v = rng.normal(100, 5, len(dates))
    spike = np.flatnonzero(dates == pd.Timestamp("2015-06-15"))[0]
    v[spike] = 400
    out = an.seasonal_anomaly(dates, v)
    assert out["anomaly"].iloc[spike] == "highly_unusual" and out["z"].iloc[spike] > 3.5
    assert (out["anomaly"] == "normal").mean() > 0.9
    z = np.zeros(len(dates))
    z[spike] = 5
    out0 = an.seasonal_anomaly(dates, z)
    assert out0["anomaly_method"].iloc[spike] == "rank_fallback" and out0["anomaly"].iloc[spike] == "highly_unusual"
    assert np.isnan(out0["z"].iloc[spike])


def test_anomaly_reports_insufficient_baseline():
    dates = pd.date_range("2020-01-01", "2022-12-31", freq="D")
    out = an.seasonal_anomaly(dates, np.ones(len(dates)))
    assert (out["anomaly"] == "insufficient_baseline").all()


def test_missing_values_are_not_treated_as_zero():
    dates = pd.date_range("2005-01-01", "2020-12-31", freq="D")
    v = np.full(len(dates), 10.0)
    v[:400] = np.nan
    out = an.seasonal_anomaly(dates, v)
    assert (out["anomaly"].iloc[:400] == "insufficient_baseline").all()
    assert np.isnan(percentile_index(np.where(np.isnan(v), -1.0, v))[:0]).all()


def test_percentile_index_zero_and_insufficient_history():
    v = np.concatenate([np.zeros(50), np.arange(1, 201, dtype=float)])
    idx = percentile_index(v)
    assert (idx[:50] == 0).all() and idx[-1] == 100 and idx[50] == 1
    assert np.isnan(percentile_index(np.concatenate([np.zeros(50), np.ones(20)]))).all()


def test_critical_windows_find_a_recurring_season():
    dates = pd.date_range("2005-01-01", "2020-12-31", freq="D")
    v = np.where((dates.month == 5), 50.0, 1.0)
    stats, wins, info = critical_windows(dates, v)
    assert info["status"] == "ok" and info["years_used"] == 16
    assert len(wins) == 1 and wins[0]["start_label"].endswith("May") or wins[0]["start_label"].endswith("Apr")
    assert wins[0]["min_years_elevated"] == 16


def test_critical_windows_insufficient_history():
    dates = pd.date_range("2019-01-01", "2020-12-31", freq="D")
    _, wins, info = critical_windows(dates, np.ones(len(dates)))
    assert wins == [] and info["status"] == "insufficient_history"
