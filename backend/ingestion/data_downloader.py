"""Resumable, verified downloader for FIRMS archive files, FIRMS API data and boundaries.

Guarantees
- Raw files are written once and never modified afterwards.
- Downloads go to ``<name>.part`` and are renamed only after validation passes.
- Interrupted downloads resume with HTTP Range requests.
- Every verified file is recorded in ``data/metadata/manifest.json`` with a SHA-256.
- Files already verified (same size and checksum) are skipped on rerun.
- The FIRMS MAP_KEY never appears in logs, the manifest or exceptions.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from backend import config

log = logging.getLogger("firesight.download")

# One shared session keeps the TLS connection open between files, which avoids a new
# (and on unstable links, slow) connection for every request.
SESSION = requests.Session()


# ----------------------------------------------------------------------------- helpers
def setup_logging() -> None:
    config.LOGS.mkdir(parents=True, exist_ok=True)
    if log.handlers:
        return
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(config.LOGS / "download.log", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    log.addHandler(fh)
    log.addHandler(sh)
    log.setLevel(logging.INFO)


def redact(text: str, key: str | None) -> str:
    """Remove the MAP_KEY from any string before it is logged or stored."""
    if key:
        text = text.replace(key, "<MAP_KEY>")
    return text


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rel(path: Path) -> str:
    return path.relative_to(config.ROOT).as_posix()


# ----------------------------------------------------------------------------- manifest
MANIFEST = config.METADATA / "manifest.json"


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {}


def save_manifest(m: dict) -> None:
    config.METADATA.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(m, indent=1, sort_keys=True), encoding="utf-8")
    for attempt in range(20):  # Windows refuses the swap while another process has the file open
        try:
            tmp.replace(MANIFEST)
            return
        except PermissionError:
            time.sleep(0.25 * (attempt + 1))
    tmp.replace(MANIFEST)


def already_verified(m: dict, dest: Path) -> bool:
    e = m.get(rel(dest))
    if not e or e.get("status") != "Verified" or not dest.exists():
        return False
    if dest.stat().st_size != e["file_size"]:
        return False
    return sha256_of(dest) == e["checksum"]


# ----------------------------------------------------------------------------- transfer
def fetch_to_part(url: str, part: Path, *, key: str | None = None, expected_size: int | None = None,
                  max_attempts: int = 8, timeout: int = 60) -> requests.Response:
    """Download ``url`` into ``part`` with resume and exponential backoff.

    Returns the last response (for headers). Raises RuntimeError after max_attempts.
    """
    part.parent.mkdir(parents=True, exist_ok=True)
    safe = redact(url, key)
    last_err = "unknown"
    for attempt in range(1, max_attempts + 1):
        have = part.stat().st_size if part.exists() else 0
        if expected_size and have == expected_size:
            return None  # complete from an earlier attempt
        if expected_size and have > expected_size:
            part.unlink()
            have = 0
        headers = {"User-Agent": config.USER_AGENT}
        if have:
            headers["Range"] = f"bytes={have}-"
        try:
            with SESSION.get(url, headers=headers, stream=True, timeout=timeout) as r:
                if r.status_code == 416:  # range not satisfiable -> restart
                    part.unlink(missing_ok=True)
                    raise IOError("range not satisfiable; restarting")
                if r.status_code in (429, 500, 502, 503, 504):
                    raise IOError(f"HTTP {r.status_code}")
                if r.status_code not in (200, 206):
                    # permanent error: do not retry
                    raise RuntimeError(f"HTTP {r.status_code} for {safe}: {r.text[:200]!r}")
                mode = "ab" if (have and r.status_code == 206) else "wb"
                got = 0
                with open(part, mode) as f:
                    for chunk in r.iter_content(1 << 16):
                        f.write(chunk)
                        got += len(chunk)
                size = part.stat().st_size
                if expected_size and size != expected_size:
                    raise IOError(f"incomplete: {size} of {expected_size} bytes")
                if attempt > 1 or have:
                    log.info("completed %s after %d attempt(s), resumed from %d bytes", safe, attempt, have)
                return r
        except RuntimeError:
            raise
        except Exception as e:  # network errors, timeouts, incomplete bodies
            last_err = redact(f"{type(e).__name__}: {e}", key)
            wait = min(60, 2 ** attempt)
            log.warning("attempt %d/%d failed for %s (%s); retrying in %ds",
                        attempt, max_attempts, safe, last_err[:160], wait)
            time.sleep(wait)
    raise RuntimeError(f"gave up on {safe} after {max_attempts} attempts: {last_err}")


# ----------------------------------------------------------------------------- validation
def validate_firms_csv(path: Path, family: str | None = None, allow_empty: bool = False) -> dict:
    """Check that ``path`` is a genuine FIRMS CSV and summarise it.

    Uses only the csv module so the result does not depend on dtype inference.
    Raises ValueError when the file is not valid.
    """
    with open(path, "rb") as f:
        head = f.read(400).lstrip()
    if head[:1] in (b"<", b"{") or b"<html" in head.lower():
        raise ValueError(f"not a CSV (looks like HTML/JSON): {head[:120]!r}")
    stats = {"rows": 0, "min_date": None, "max_date": None, "duplicates": 0, "missing_values": 0,
             "satellites": {}, "lat_min": None, "lat_max": None, "lon_min": None, "lon_max": None}
    seen = set()
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header or "latitude" not in header or "acq_date" not in header:
            raise ValueError(f"unexpected header: {header}")
        if family:
            want = config.ARCHIVE_COLUMNS[family]
            if header != want:
                raise ValueError(f"header differs from expected {family} archive layout: {header}")
        stats["columns"] = header
        i_lat, i_lon = header.index("latitude"), header.index("longitude")
        i_date, i_sat = header.index("acq_date"), header.index("satellite")
        n = len(header)
        for row in reader:
            if len(row) != n:
                raise ValueError(f"row {stats['rows'] + 2} has {len(row)} fields, expected {n}")
            stats["rows"] += 1
            if any(v == "" for v in row):
                stats["missing_values"] += 1
            k = hash(tuple(row))
            if k in seen:
                stats["duplicates"] += 1
            else:
                seen.add(k)
            d = row[i_date]
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
                raise ValueError(f"bad acq_date {d!r} at row {stats['rows'] + 1}")
            if stats["min_date"] is None or d < stats["min_date"]:
                stats["min_date"] = d
            if stats["max_date"] is None or d > stats["max_date"]:
                stats["max_date"] = d
            lat, lon = float(row[i_lat]), float(row[i_lon])
            for name, v, fn in (("lat_min", lat, min), ("lat_max", lat, max),
                                ("lon_min", lon, min), ("lon_max", lon, max)):
                stats[name] = v if stats[name] is None else fn(stats[name], v)
            s = row[i_sat]
            stats["satellites"][s] = stats["satellites"].get(s, 0) + 1
    if stats["rows"] == 0 and not allow_empty:
        raise ValueError("header only, no data rows")
    return stats


# ----------------------------------------------------------------------------- catalogue
def fetch_catalogue() -> list[dict]:
    """Download (or reuse today's copy of) the FIRMS yearly country-file catalogue."""
    dest = config.METADATA / "yearly_summary_files.txt"
    fresh = dest.exists() and (time.time() - dest.stat().st_mtime) < 86400
    if not fresh:
        part = dest.with_suffix(".txt.part")
        part.unlink(missing_ok=True)
        fetch_to_part(config.CATALOGUE_URL, part)
        with open(part, "r", encoding="utf-8") as f:
            if not f.readline().startswith("filename,size"):
                raise ValueError("catalogue has an unexpected header")
        part.replace(dest)
        log.info("catalogue saved: %s", rel(dest))
    with open(dest, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def archive_targets(country: str, catalogue: list[dict]) -> list[dict]:
    out = []
    pat = re.compile(r"^(modis|viirs-snpp|viirs-jpss1)_(\d{4})_(.+)\.csv$")
    for row in catalogue:
        m = pat.match(row["filename"])
        if not m or m[3] != country:
            continue
        code, year = m[1], int(m[2])
        info = config.ARCHIVE_PRODUCTS[code]
        out.append({
            "code": code, "year": year, "filename": row["filename"],
            "expected_size": int(row["size"]), "catalogue_updated": row["updated"],
            "url": f"{config.FIRMS_BASE}/data/country/{code}/{year}/{row['filename']}",
            "dest": config.RAW / info["folder"] / row["filename"],
            "product": info["product"], "satellite": info["satellite"],
        })
    return sorted(out, key=lambda t: (t["code"], t["year"]))


def download_archive_file(t: dict, manifest: dict) -> dict:
    dest: Path = t["dest"]
    key = rel(dest)
    if already_verified(manifest, dest):
        log.info("skip (verified): %s", key)
        return manifest[key]
    part = dest.with_name(dest.name + ".part")
    entry = {"source": "FIRMS country archive", "product": t["product"], "satellite": t["satellite"],
             "processing": "SP", "year": t["year"], "filename": t["filename"], "source_url": t["url"],
             "catalogue_size": t["expected_size"], "catalogue_updated": t["catalogue_updated"]}
    try:
        r = fetch_to_part(t["url"], part, expected_size=t["expected_size"])
        family = "modis" if t["code"] == "modis" else "viirs"
        stats = validate_firms_csv(part, family)
        years = {stats["min_date"][:4], stats["max_date"][:4]}
        if years != {str(t["year"])}:
            raise ValueError(f"dates {stats['min_date']}..{stats['max_date']} outside year {t['year']}")
        part.replace(dest)
        entry.update(stats, status="Verified", file_size=dest.stat().st_size,
                     checksum=sha256_of(dest), retrieval_date=now_utc(),
                     content_type=(r.headers.get("Content-Type") if r is not None else None))
        log.info("verified %s: %d rows, %s..%s, %d bytes", key, stats["rows"],
                 stats["min_date"], stats["max_date"], entry["file_size"])
    except Exception as e:
        entry.update(status="Failed", error=str(e)[:300], retrieval_date=now_utc())
        log.error("FAILED %s: %s", key, str(e)[:300])
    manifest[key] = entry
    save_manifest(manifest)
    return entry


# ----------------------------------------------------------------------------- boundaries
def download_boundaries(iso3: str, manifest: dict) -> list[dict]:
    out = []
    for level in ("ADM0", "ADM1", "ADM2"):
        dest = config.BOUNDARIES / f"geoBoundaries-{iso3}-{level}.geojson"
        key = rel(dest)
        if already_verified(manifest, dest):
            log.info("skip (verified): %s", key)
            out.append(manifest[key])
            continue
        entry = {"source": "geoBoundaries gbOpen", "product": "boundary", "satellite": "",
                 "processing": "", "year": "", "filename": dest.name}
        try:
            meta = None
            for attempt in range(1, 7):
                try:
                    r = SESSION.get(f"https://www.geoboundaries.org/api/current/gbOpen/{iso3}/{level}/",
                                     headers={"User-Agent": config.USER_AGENT}, timeout=60)
                    r.raise_for_status()
                    meta = r.json()
                    break
                except Exception as e:
                    log.warning("geoBoundaries metadata %s attempt %d failed: %s", level, attempt, e)
                    time.sleep(min(60, 2 ** attempt))
            if meta is None:
                raise RuntimeError("could not read geoBoundaries metadata")
            (config.BOUNDARIES / f"geoBoundaries-{iso3}-{level}-metadata.json").parent.mkdir(parents=True, exist_ok=True)
            (config.BOUNDARIES / f"geoBoundaries-{iso3}-{level}-metadata.json").write_text(
                json.dumps(meta, indent=1), encoding="utf-8")
            url = meta["gjDownloadURL"]
            part = dest.with_name(dest.name + ".part")
            part.unlink(missing_ok=True)  # GitHub raw redirects; restart rather than resume
            fetch_to_part(url, part)
            gj = json.loads(part.read_text(encoding="utf-8"))
            n = len(gj.get("features", []))
            if gj.get("type") != "FeatureCollection" or n == 0:
                raise ValueError("not a non-empty GeoJSON FeatureCollection")
            part.replace(dest)
            entry.update(status="Verified", source_url=url, rows=n, file_size=dest.stat().st_size,
                         checksum=sha256_of(dest), retrieval_date=now_utc(),
                         license=meta.get("boundaryLicense"), boundary_source=meta.get("boundarySource"),
                         boundary_year=meta.get("boundaryYearRepresented"), build_date=meta.get("buildDate"),
                         declared_units=meta.get("admUnitCount"))
            log.info("verified %s: %d features", key, n)
        except Exception as e:
            entry.update(status="Failed", error=str(e)[:300], retrieval_date=now_utc())
            log.error("FAILED %s: %s", key, str(e)[:300])
        manifest[key] = entry
        save_manifest(manifest)
        out.append(entry)
    return out


# ----------------------------------------------------------------------------- FIRMS API
def api_get_text(path: str, key: str, max_attempts: int = 6) -> str:
    url = f"{config.FIRMS_BASE}{path}"
    last = ""
    for attempt in range(1, max_attempts + 1):
        try:
            r = SESSION.get(url, headers={"User-Agent": config.USER_AGENT}, timeout=90)
            if r.status_code in (429, 500, 502, 503, 504):
                raise IOError(f"HTTP {r.status_code}")
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {redact(r.text[:200], key)}")
            return r.text
        except RuntimeError:
            raise
        except Exception as e:
            last = redact(str(e), key)
            wait = min(90, 3 ** attempt)
            log.warning("API attempt %d failed for %s (%s); retry in %ds", attempt, redact(path, key), last[:120], wait)
            time.sleep(wait)
    raise RuntimeError(f"API gave up on {redact(path, key)}: {last}")


def fetch_data_availability(key: str) -> list[dict]:
    """Return rows of data_id/min_date/max_date and save them to metadata."""
    text = api_get_text(f"/api/data_availability/csv/{key}/all", key)
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows or "data_id" not in rows[0]:
        raise ValueError(f"unexpected data_availability response: {redact(text[:200], key)!r}")
    dest = config.METADATA / "firms_data_availability.csv"
    dest.write_text(text, encoding="utf-8")
    log.info("data availability saved: %s (%d sources)", rel(dest), len(rows))
    return rows


def download_api_range(source: str, bbox: tuple, start: date, end: date, key: str,
                       manifest: dict, label: str) -> list[dict]:
    """Download ``source`` for ``bbox`` in 5-day chunks, one raw file per chunk, resumable."""
    folder, product, satellite, processing = config.API_SOURCES[source]
    area = ",".join(str(v) for v in bbox)
    out = []
    cur = start
    while cur <= end:
        days = min(5, (end - cur).days + 1)
        dest = config.RAW / folder / label / source / f"{source}_{label}_{cur.isoformat()}_{days}d.csv"
        mkey = rel(dest)
        chunk_end = cur + timedelta(days=days - 1)
        # A chunk that could still receive data (ends within the last 2 days) is refreshed.
        final = chunk_end < date.today() - timedelta(days=2)
        if final and already_verified(manifest, dest):
            out.append(manifest[mkey])
            cur += timedelta(days=days)
            continue
        entry = {"source": "FIRMS area API", "product": product, "satellite": satellite,
                 "processing": processing, "year": cur.year, "filename": dest.name,
                 "source_url": f"{config.FIRMS_BASE}/api/area/csv/<MAP_KEY>/{source}/{area}/{days}/{cur.isoformat()}"}
        try:
            text = api_get_text(f"/api/area/csv/{key}/{source}/{area}/{days}/{cur.isoformat()}", key)
            dest.parent.mkdir(parents=True, exist_ok=True)
            part = dest.with_name(dest.name + ".part")
            part.write_text(text, encoding="utf-8", newline="")
            stats = validate_firms_csv(part, allow_empty=True)
            part.replace(dest)
            entry.update(stats, status="Verified", file_size=dest.stat().st_size,
                         checksum=sha256_of(dest), retrieval_date=now_utc(), final=final)
        except Exception as e:
            entry.update(status="Failed", error=redact(str(e), key)[:300], retrieval_date=now_utc())
            log.error("FAILED %s: %s", mkey, entry["error"])
        manifest[mkey] = entry
        save_manifest(manifest)
        out.append(entry)
        cur += timedelta(days=days)
        time.sleep(0.3)  # stay far below 5000 transactions / 10 min
    ok = sum(1 for e in out if e["status"] == "Verified")
    log.info("%s %s..%s: %d/%d chunks verified, %d rows", source, start, end, ok, len(out),
             sum(e.get("rows", 0) for e in out))
    return out
