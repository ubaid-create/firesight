"""Build data/metadata/data_inventory.csv from the download manifest."""
from __future__ import annotations

import csv

from backend import config
from backend.ingestion.data_downloader import load_manifest

COLUMNS = ["source", "product", "satellite", "processing", "year", "filename", "path", "file_size",
           "rows", "min_date", "max_date", "duplicates", "missing_values", "satellites",
           "retrieval_date", "checksum", "status", "source_url", "error"]


def write_inventory() -> list[dict]:
    m = load_manifest()
    rows = []
    for path, e in sorted(m.items()):
        r = {c: e.get(c, "") for c in COLUMNS}
        r["path"] = path
        sats = e.get("satellites")
        r["satellites"] = ";".join(f"{k}={v}" for k, v in sorted(sats.items())) if sats else ""
        rows.append(r)
    dest = config.METADATA / "data_inventory.csv"
    with open(dest, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return rows


def summarise(rows: list[dict]) -> str:
    groups: dict[tuple, dict] = {}
    for r in rows:
        if r["product"] == "boundary":
            continue
        k = (r["source"], r["product"], r["satellite"], r["processing"])
        g = groups.setdefault(k, {"files": 0, "ok": 0, "rows": 0, "bytes": 0, "min": None, "max": None,
                                  "dups": 0, "missing": 0})
        g["files"] += 1
        if r["status"] == "Verified":
            g["ok"] += 1
            g["rows"] += int(r["rows"] or 0)
            g["bytes"] += int(r["file_size"] or 0)
            g["dups"] += int(r["duplicates"] or 0)
            g["missing"] += int(r["missing_values"] or 0)
            if r["min_date"]:
                g["min"] = min(g["min"], r["min_date"]) if g["min"] else r["min_date"]
                g["max"] = max(g["max"], r["max_date"]) if g["max"] else r["max_date"]
    lines = []
    for k, g in sorted(groups.items()):
        lines.append(f"{k[0]} | {k[1]} {k[2]} {k[3]} | files {g['ok']}/{g['files']} verified | "
                     f"rows {g['rows']:,} | {g['bytes'] / 1e6:.1f} MB | {g['min']}..{g['max']} | "
                     f"duplicate rows {g['dups']} | rows with empty fields {g['missing']}")
    return "\n".join(lines)
