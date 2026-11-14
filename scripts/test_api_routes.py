"""Small, safe probes of the FIRMS API before any bulk request. Never prints the key."""
import csv, datetime, io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import config
from backend.ingestion import data_downloader as dl

dl.setup_logging()
key = config.load_map_key()
if not key:
    raise SystemExit("FIRMS_MAP_KEY missing in .env")
av = {r["data_id"]: r for r in dl.fetch_data_availability(key)}
for k, r in sorted(av.items()):
    print("AVAIL", k, r["min_date"], r["max_date"])
bbox = ",".join(str(v) for v in config.COUNTRIES["Pakistan"]["bbox"])


def test(src, day, n=5):
    try:
        t = dl.api_get_text(f"/api/area/csv/{key}/{src}/{bbox}/{n}/{day}", key)
    except Exception as e:
        print("TEST", src, day, "ERROR", dl.redact(str(e), key)[:200])
        return
    rows = list(csv.reader(io.StringIO(t)))
    hdr = rows[0] if rows else []
    body = rows[1:]
    dates = sorted({r[hdr.index("acq_date")] for r in body}) if body and "acq_date" in hdr else []
    sats = sorted({r[hdr.index("satellite")] for r in body}) if body and "satellite" in hdr else []
    print("TEST", src, day, f"{n}d rows={len(body)} dates={dates[:1]}..{dates[-1:]} sats={sats}")
    print("   header", hdr)
    if body:
        print("   first", body[0])
    else:
        print("   raw", repr(dl.redact(t[:200], key)))


test("VIIRS_NOAA21_SP", "2024-05-01")
for src in ("VIIRS_NOAA21_NRT", "VIIRS_NOAA20_NRT", "MODIS_NRT", "VIIRS_SNPP_NRT"):
    if src in av:
        test(src, (datetime.date.fromisoformat(av[src]["max_date"]) - datetime.timedelta(days=4)).isoformat())
for src in ("VIIRS_NOAA20_SP", "MODIS_SP", "VIIRS_SNPP_SP"):
    if src in av:
        test(src, "2026-03-01")
