"""API tests against the real processed data (skipped if the pipeline has not been run)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import config  # noqa: E402

pytestmark = pytest.mark.skipif(not (config.PROCESSED / "web" / "detections_web.parquet").exists(),
                                reason="processed data not present")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from backend.api.main import app
    return TestClient(app)


def test_meta_and_aois(client):
    m = client.get("/api/meta").json()
    assert m["latest_date"] >= "2026-11-01" and m["links"]["MODIS_to_SNPP"]["status"] == "fitted"
    a = client.get("/api/aois").json()
    levels = pd.Series([x["level"] for x in a]).value_counts().to_dict()
    assert levels["ADM0"] == 1 and levels["ADM1"] == 7 and levels["ADM2"] == 126 and levels.get("STORY") == 1


def test_calendar_matches_parquet(client):
    c = client.get("/api/calendar", params={"aoi": "PAK-ADM1-5"}).json()
    h = pd.read_parquet(config.PROCESSED / "harmonized" / "harmonized_daily.parquet",
                        filters=[("aoi_id", "==", "PAK-ADM1-5")]).sort_values("date")
    assert c["n"] == len(h) and c["start"] == str(h["date"].iloc[0].date())
    v = np.array([np.nan if x is None else x for x in c["value"]])
    assert np.allclose(v, h["h_roll"].to_numpy(), atol=0.01, equal_nan=True)
    assert set(c["method"]) <= {0, 1, 2, 3, 4, 5}


def test_calendar_raw_mode_is_observed_cells(client):
    c = client.get("/api/calendar", params={"aoi": "PAK", "measure": "raw", "platform": "Aqua"}).json()
    vals = c["value"]
    first = next(i for i, x in enumerate(vals) if x is not None)
    assert pd.Timestamp(c["start"]) + pd.Timedelta(days=first) == pd.Timestamp("2002-07-06") or vals[first] >= 0
    assert all(i is None for i in c["index"])


def test_missing_is_not_zero(client):
    c = client.get("/api/calendar", params={"aoi": "PAK", "measure": "raw", "platform": "NOAA21"}).json()
    assert c["value"][0] is None and c["method"][0] == 0 and c["zero"][0] == 0


def test_day_detail_and_hotspots(client):
    d = client.get("/api/day", params={"aoi": "PAK", "date": "2022-05-20"}).json()
    assert {p["platform"] for p in d["platforms"]} == {"Terra", "Aqua", "SNPP", "NOAA20", "NOAA21"}
    assert d["harmonized"]["carrier"] == "SNPP"
    h = client.get("/api/hotspots", params={"aoi": "STORY-SHERANI", "start": "2022-05-10", "end": "2022-05-31"}).json()
    assert h["returned"] > 50 and set(h["cols"]["p"]) >= {"SNPP", "NOAA20"}
    one = client.get(f"/api/hotspot/{h['cols']['id'][0]}").json()
    assert one["source_file"].startswith("data/raw/")


def test_filters_reduce_counts(client):
    base = {"aoi": "PAK-ADM1-5", "start": "2025-11-01", "end": "2025-11-10"}
    allp = client.get("/api/hotspots", params=base).json()["total"]
    viirs = client.get("/api/hotspots", params={**base, "platforms": "SNPP"}).json()["total"]
    night = client.get("/api/hotspots", params={**base, "daynight": "N"}).json()["total"]
    assert 0 < viirs < allp and 0 <= night < allp


def test_compare_like_for_like(client):
    c = client.get("/api/compare", params={"aoi": "PAK", "days": 14}).json()
    assert c["years_used"] >= 20 and all(h["year"] < 2026 for h in c["history"])
    assert c["provisional_days"] > 0  # latest weeks rest on NRT data


def test_series_windows_anomalies_validation_export(client):
    s = client.get("/api/series", params={"aoi": "PAK", "freq": "year"}).json()
    assert s["period"][0].startswith("2000") and len(s["harmonized"]) == len(s["period"])
    assert client.get("/api/windows", params={"aoi": "PAK"}).json()["windows"]
    assert client.get("/api/anomalies", params={"aoi": "PAK"}).json()["episodes"]
    v = client.get("/api/validation").json()
    assert "MODIS_to_SNPP" in v["links"]
    r = client.get("/api/export.csv", params={"aoi": "PAK-ADM1-0", "start": "2022-05-01", "end": "2022-05-31"})
    assert r.status_code == 200 and r.text.splitlines()[0].startswith("aoi_id,aoi_name,date")
    assert len(r.text.splitlines()) == 32


def test_custom_aoi_inside_and_outside(client):
    inside = client.post("/api/custom", json={"type": "bbox", "bbox": [73.9, 31.3, 74.5, 31.7]}).json()
    assert inside["coverage"] == "pakistan_processed" and inside["harmonized"]
    cal = client.get("/api/calendar", params={"aoi": inside["aoi_id"]}).json()
    assert cal["n"] > 9000
    outside = client.post("/api/custom", json={"type": "bbox", "bbox": [10, 45, 11, 46]}).json()
    assert outside["coverage"] == "not_acquired" and not outside["harmonized"]
    assert client.get("/api/calendar", params={"aoi": outside["aoi_id"]}).status_code == 409


def test_stories(client):
    s = client.get("/api/stories").json()
    sh = next(x for x in s if x["id"] == "sherani-2022")
    assert sh["stats"]["first_detection"] >= "2022-05-01" and sh["stats"]["detections_by_platform"]
