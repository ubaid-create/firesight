"""Tests for download validation, manifest skipping and key redaction."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import config  # noqa: E402
from backend.ingestion import data_downloader as dl  # noqa: E402

MODIS_HEADER = ",".join(config.ARCHIVE_COLUMNS["modis"])
ROW1 = "29.1797,71.4212,307.2,1.2,1.1,2023-01-01,0827,Aqua,MODIS,44,61.03,297.1,7,D,0"
ROW2 = "29.9005,72.835,304.6,1,1,2023-01-02,0827,Terra,MODIS,58,61.03,294.4,4.4,D,0"


def write(tmp_path, text, name="f.csv"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_valid_csv_summary(tmp_path):
    s = dl.validate_firms_csv(write(tmp_path, "\n".join([MODIS_HEADER, ROW1, ROW2, ROW1]) + "\n"), "modis")
    assert s["rows"] == 3
    assert s["duplicates"] == 1
    assert (s["min_date"], s["max_date"]) == ("2023-01-01", "2023-01-02")
    assert s["satellites"] == {"Aqua": 2, "Terra": 1}
    assert s["lat_min"] == pytest.approx(29.1797)


def test_rejects_html_and_json(tmp_path):
    with pytest.raises(ValueError):
        dl.validate_firms_csv(write(tmp_path, "<html><body>Error</body></html>"))
    with pytest.raises(ValueError):
        dl.validate_firms_csv(write(tmp_path, '{"status":404,"title":"File Not Found"}'))


def test_rejects_header_only_unless_allowed(tmp_path):
    p = write(tmp_path, MODIS_HEADER + "\n")
    with pytest.raises(ValueError):
        dl.validate_firms_csv(p, "modis")
    assert dl.validate_firms_csv(p, "modis", allow_empty=True)["rows"] == 0


def test_rejects_wrong_layout_and_truncated_row(tmp_path):
    with pytest.raises(ValueError):
        dl.validate_firms_csv(write(tmp_path, "\n".join([MODIS_HEADER, ROW1]) + "\n"), "viirs")
    with pytest.raises(ValueError):
        dl.validate_firms_csv(write(tmp_path, "\n".join([MODIS_HEADER, ROW1, "29.1,71.4,307"]) + "\n"), "modis")


def test_redact_removes_key():
    assert "SECRET123" not in dl.redact("https://x/api/area/csv/SECRET123/MODIS_SP", "SECRET123")
    assert dl.redact("abc", None) == "abc"


def test_already_verified_detects_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    p = write(tmp_path, "\n".join([MODIS_HEADER, ROW1]) + "\n")
    m = {dl.rel(p): {"status": "Verified", "file_size": p.stat().st_size, "checksum": dl.sha256_of(p)}}
    assert dl.already_verified(m, p)
    p.write_text("\n".join([MODIS_HEADER, ROW2]) + "\n", encoding="utf-8")
    assert not dl.already_verified(m, p)
    assert not dl.already_verified({}, p)
