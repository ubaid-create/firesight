"""Central paths and source definitions for FireSight."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
BOUNDARIES = DATA / "boundaries"
PROCESSED = DATA / "processed"
METADATA = DATA / "metadata"
LOGS = METADATA / "logs"

FIRMS_BASE = "https://firms.modaps.eosdis.nasa.gov"
CATALOGUE_URL = f"{FIRMS_BASE}/data/country/yearly_summary_files.txt"
USER_AGENT = "FireSight/0.1 (NASA Space Apps 2026 project)"

# FIRMS country-archive product code -> local folder and description.
ARCHIVE_PRODUCTS = {
    "modis": {"folder": "modis", "product": "MODIS", "satellite": "Terra+Aqua"},
    "viirs-snpp": {"folder": "viirs_snpp", "product": "VIIRS", "satellite": "SNPP"},
    "viirs-jpss1": {"folder": "viirs_noaa20", "product": "VIIRS", "satellite": "NOAA-20"},
}

ARCHIVE_COLUMNS = {
    "modis": ["latitude", "longitude", "brightness", "scan", "track", "acq_date", "acq_time",
              "satellite", "instrument", "confidence", "version", "bright_t31", "frp",
              "daynight", "type"],
    "viirs": ["latitude", "longitude", "bright_ti4", "scan", "track", "acq_date", "acq_time",
              "satellite", "instrument", "confidence", "version", "bright_ti5", "frp",
              "daynight", "type"],
}

# FIRMS API sources -> local folder (standard and NRT kept apart).
API_SOURCES = {
    "MODIS_SP": ("api_sp", "MODIS", "Terra+Aqua", "SP"),
    "VIIRS_SNPP_SP": ("api_sp", "VIIRS", "SNPP", "SP"),
    "VIIRS_NOAA20_SP": ("api_sp", "VIIRS", "NOAA-20", "SP"),
    "VIIRS_NOAA21_SP": ("viirs_noaa21", "VIIRS", "NOAA-21", "SP"),
    "MODIS_NRT": ("nrt", "MODIS", "Terra+Aqua", "NRT"),
    "VIIRS_SNPP_NRT": ("nrt", "VIIRS", "SNPP", "NRT"),
    "VIIRS_NOAA20_NRT": ("nrt", "VIIRS", "NOAA-20", "NRT"),
    "VIIRS_NOAA21_NRT": ("nrt", "VIIRS", "NOAA-21", "NRT"),
}

# Country presets: FIRMS archive name, ISO3 for geoBoundaries, bbox W,S,E,N.
COUNTRIES = {
    "Pakistan": {"iso3": "PAK", "bbox": (60.5, 23.5, 77.8, 37.1)},
}


def load_map_key() -> str | None:
    """Read FIRMS_MAP_KEY from the environment or .env. Never log the value."""
    key = os.environ.get("FIRMS_MAP_KEY")
    if not key:
        env = ROOT / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("FIRMS_MAP_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key or key == "YOUR_FIRMS_MAP_KEY":
        return None
    return key
