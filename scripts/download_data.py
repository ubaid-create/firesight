"""FireSight data acquisition.

Examples (run from the project root with the virtual environment's Python):
  python scripts/download_data.py --samples            # one file per product, validated
  python scripts/download_data.py --archive            # full country archive
  python scripts/download_data.py --boundaries
  python scripts/download_data.py --availability       # needs FIRMS_MAP_KEY in .env
  python scripts/download_data.py --recent 60          # last N days via the API (needs key)
  python scripts/download_data.py --inventory          # rebuild data_inventory.csv only
Safe to rerun: verified files are skipped.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import config  # noqa: E402
from backend.ingestion import data_downloader as dl  # noqa: E402
from backend.ingestion.data_inventory import summarise, write_inventory  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default="Pakistan")
    ap.add_argument("--samples", action="store_true")
    ap.add_argument("--sample-year", type=int, default=2023)
    ap.add_argument("--archive", action="store_true")
    ap.add_argument("--boundaries", action="store_true")
    ap.add_argument("--availability", action="store_true")
    ap.add_argument("--recent", type=int, metavar="DAYS")
    ap.add_argument("--api-full", action="store_true",
                    help="NOAA-21 SP full period, 2026 SP for all platforms, NRT for the gap after SP")
    ap.add_argument("--inventory", action="store_true")
    a = ap.parse_args()

    dl.setup_logging()
    manifest = dl.load_manifest()
    failed = 0

    if a.samples or a.archive:
        targets = dl.archive_targets(a.country, dl.fetch_catalogue())
        if a.samples and not a.archive:
            targets = [t for t in targets if t["year"] == a.sample_year]
        dl.log.info("%d archive file(s) to check for %s", len(targets), a.country)
        for i, t in enumerate(targets, 1):
            e = dl.download_archive_file(t, manifest)
            failed += e["status"] != "Verified"
            dl.log.info("progress %d/%d", i, len(targets))

    if a.boundaries:
        for e in dl.download_boundaries(config.COUNTRIES[a.country]["iso3"], manifest):
            failed += e["status"] != "Verified"

    if a.availability or a.recent or a.api_full:
        key = config.load_map_key()
        if not key:
            dl.log.error("FIRMS_MAP_KEY is not set in .env; API steps skipped")
            failed += 1
        else:
            avail = {r["data_id"]: r for r in dl.fetch_data_availability(key)}
            for k, r in sorted(avail.items()):
                dl.log.info("availability %s: %s .. %s", k, r["min_date"], r["max_date"])
            if a.api_full:
                bbox = config.COUNTRIES[a.country]["bbox"]
                plan = []
                for src, (_f, _p, sat, proc) in config.API_SOURCES.items():
                    if src not in avail:
                        continue
                    lo = date.fromisoformat(avail[src]["min_date"])
                    hi = min(date.today(), date.fromisoformat(avail[src]["max_date"]))
                    if proc == "SP":
                        # NOAA-21 is not in the country archive: fetch its whole standard record.
                        # Other platforms: only 2026, since 2000-2025 came from the archive.
                        if sat != "NOAA-21":
                            lo = max(lo, date(2026, 1, 1))
                    else:
                        sp = src.replace("_NRT", "_SP")
                        if sp in avail:  # NRT only for the gap after standard data ends
                            lo = max(lo, date.fromisoformat(avail[sp]["max_date"]) + timedelta(days=1))
                    if lo <= hi:
                        plan.append((src, lo, hi))
                total = sum(((hi - lo).days + 5) // 5 for _s, lo, hi in plan)
                dl.log.info("API plan: %d sources, about %d requests", len(plan), total)
                for src, lo, hi in plan:
                    dl.log.info("API plan %s: %s .. %s", src, lo, hi)
                    for e in dl.download_api_range(src, bbox, lo, hi, key, manifest, a.country):
                        failed += e["status"] != "Verified"
            if a.recent:
                bbox = config.COUNTRIES[a.country]["bbox"]
                start = date.today() - timedelta(days=a.recent)
                for src in config.API_SOURCES:
                    if src not in avail:
                        continue
                    lo = max(start, date.fromisoformat(avail[src]["min_date"]))
                    hi = min(date.today(), date.fromisoformat(avail[src]["max_date"]))
                    if lo > hi:
                        dl.log.info("%s: nothing available in the requested window", src)
                        continue
                    for e in dl.download_api_range(src, bbox, lo, hi, key, manifest, a.country):
                        failed += e["status"] != "Verified"

    rows = write_inventory()
    print("\n=== inventory summary ===")
    print(summarise(rows))
    print(f"\ninventory: {dl.rel(config.METADATA / 'data_inventory.csv')}  entries: {len(rows)}  failed this run: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
