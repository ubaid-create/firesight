# FireSight

**Harmonized MODIS and VIIRS Satellite Fire Intelligence Platform**

NASA Space Apps Challenge 2026 · Challenge: *Harmonization of MODIS and VIIRS Hot Spots* · Team FireSight

![Dashboard](docs/screenshots/01_dashboard_pakistan.png)

## The problem

NASA FIRMS has recorded active-fire hotspots since November 2000. The record comes from five satellites with different instruments, pixel sizes and overpass times:

- MODIS Terra (from 2000) and Aqua (from 2002), with 1 km pixels.
- VIIRS on S-NPP (2012 – 2 Nov 2026), NOAA-20 (2018) and NOAA-21 (2023), with 375 m pixels.

Simply merging their detections creates artificial jumps every time a satellite is added. In Pakistan's FIRMS data, the naive union rises **5.5×** when S-NPP arrives in 2012, while MODIS alone rises only 1.13×. That jump comes from the satellites, not from more burning.

## What FireSight does

FireSight turns those records into **one consistent burning-activity history** for Pakistan from November 2000 to the latest available day. It shows the history as an interactive **burning calendar**, together with:

- maps;
- before/after harmonization charts;
- anomaly detection;
- recurring critical burning windows;
- a like-for-like "now vs historical median" comparison;
- guided fire stories.

Every number comes from NASA FIRMS data. Every result carries its source platform, its method (observed or reconstructed), its uncertainty and its data-quality status.

| Feature | What it shows |
|---|---|
| Burning activity calendar | Day-of-year × year heatmap of harmonized 8-day activity (2000–2026), or a single-year calendar view. Tooltips show index, interval, method, anomaly and data quality; click a day to load it on the map. A raw daily mode shows any single platform's own observations. |
| Fire map | Detections from all five platforms. Filters for platform, day/night, sensor-specific confidence, detection type and persistent sources. Also: activity-density grid, harmonized index by district or province, NASA GIBS true-colour imagery, click-through detection details with source file and row. |
| Area selection | Pakistan, 7 provinces/territories, 126 districts, custom polygons ("Draw area") and coordinate boxes. Areas outside Pakistan are marked "historical data not acquired" and can fetch recent raw FIRMS observations on demand. Pakistan's calibration is never applied to them. |
| Sensor harmonization | Naive union vs raw MODIS vs raw S-NPP vs harmonized, with platform transitions marked. Each platform's own series. Calibrated platforms against the S-NPP reference on the overlap period. |
| Historical intelligence | Seasonal pattern, critical burning windows (weeks elevated in ≥ 50% of years), latest 14 days vs the same dates in every year, ranked unusual episodes. |
| Data quality | Reliability rating per area, provisional flags for near-real-time data, FIRMS missing-data days. "No detections recorded" is shown separately from "no platform delivering". |
| Fire stories | Sherani chilgoza pine forest fire (May 2022) and Punjab's two burning seasons, running on the live application. |
| Export | Harmonized CSV with per-platform contributions, uncertainty, method, anomaly and calibration version. Raw detection CSV with source file and row. |
| Accessibility | Viridis (default), Cividis (colour-vision safe) and YlOrRd palettes. Readable on phones. |

## How the harmonization works

1. **Raw data, unchanged.** Data comes from the FIRMS country archive (MODIS C6.1 2000–2025, VIIRS S-NPP 2012–2025, NOAA-20 2018–2025) and the FIRMS Area API (NOAA-21 standard data, 2026 standard data, and the near-real-time gap). Every file is checksummed in `data/metadata/manifest.json`.
2. **Normalization.** All sensors are mapped to one schema. The original confidence, both brightness channels, pixel size, product version, source file and row are kept. Each detection gets a UTC timestamp and a local solar time.
3. **Common 1 km equal-area grid** (EPSG:6933). For each platform and day, an active cell counts once. Platforms are never summed.
4. **Calibration on 8-day windows per province.** Each platform is mapped onto the VIIRS S-NPP scale:

   | Link | Training years | Held-out test years |
   |---|---|---|
   | MODIS → S-NPP | 2012–2021 | 2022–2025 |
   | NOAA-20 → S-NPP | 2018–2022 | 2023–2025 |
   | NOAA-21 → S-NPP | Mar 2023–2024 | 2025 – Jul 2026 |
   | Terra → S-NPP (for 2000–2002) | 2012–2021 | 2022–2025 |

   The model for each link is chosen by cross-validation within the training years.
5. **Continuous record.** Which platform carries the record in each period:

   | Period | Source |
   |---|---|
   | Nov 2000 – Jul 2002 | Calibrated Terra |
   | Jul 2002 – Jan 2012 | Calibrated MODIS |
   | Jan 2012 – 2 Nov 2026 | Observed S-NPP |
   | From 3 Nov 2026 | Calibrated NOAA-21 (NOAA's primary successor) |

   Provinces sum to the country; districts receive shares of their province.
6. **Activity index, anomalies and windows.**
   - The index is a 0–100 percentile of the area's own history.
   - Anomalies use a robust seasonal z-score: (x − median) / (1.4826 × MAD), measured against the same dates ±7 days in other years.
   - A critical window is a week that is elevated in at least half of the years.

### Validation results (held-out years, computed by `validation/run_validation.py`)

| Link | Total bias before | Total bias after | Spearman | 80% interval coverage |
|---|---|---|---|---|
| MODIS → S-NPP | −73.9% | +1.0% | 0.907 | 77.2% |
| NOAA-20 → S-NPP | +5.3% | −1.3% | 0.975 | 84.5% |
| NOAA-21 → S-NPP | +2.6% | −1.2% | 0.979 | 82.9% |
| Terra → S-NPP | −89.3% | −17.3% | 0.831 | 72.4% |

How much each platform transition inflates the record, compared with a control satellite present on both sides:

| Platform added | Naive merge | Harmonized |
|---|---|---|
| Aqua (2002) | +100% | −14% |
| S-NPP (2012) | +385% | +6% |
| NOAA-20 (2018) | +79% | +3% |
| NOAA-21 (2023) | +31% | −2% |

Full results are in [docs/VALIDATION_REPORT.md](docs/VALIDATION_REPORT.md) and on the app's *Method & validation* page.

### Limitations

- **Reference scale, not ground truth.** S-NPP is the chosen reference scale. The validation measures agreement between sensors, not wildfire-detection accuracy.
- **Model selection.** The model-selection rule (cross-validated totals within 5%) was added after held-out results had been seen, so the test is not fully independent of that choice. All candidate models are reported.
- **District reliability.** District estimates are much less reliable than province or country estimates. The 8-day Spearman is 0.53 for districts versus 0.92 for provinces. Each area shows a reliability rating.
- **Terra-only years.** The Terra-only period (2000–2002) has the weakest support. Terra's orbit has drifted since 2022 (overpass about 10:50 → 09:20 local time), which affects the test years.
- **Pakistan-only calibration.** The calibration was fitted in Pakistan and is not transferable. With Punjab left out of the fit, Punjab is overestimated by 52%. It is never applied outside Pakistan.
- **Provisional recent data.** Near-real-time data after the last standard-quality date are provisional and have no detection type.
- **No detection is not no fire.** Clouds, overpass timing and detection limits all affect what is recorded.
- **Hotspots are not confirmed wildfires.** A hotspot is a thermal anomaly. Agricultural burning is included as vegetation burning.
- **Sherani boundary.** The 2019 geoBoundaries district layer does not separate Sherani district from Zhob, so the Sherani story uses an event box drawn around the detections.

## Running FireSight

Requirements: Python 3.13, Node.js 20+, about 1 GB of disk space, internet access for the first download.

1. Create the Python environment with Python 3.13 (on Windows `py -3.13`; on macOS or Linux `python3.13`).

   ```bash
   py -3.13 -m venv .venv
   ```

   ```bash
   .venv/Scripts/python -m pip install -r requirements.txt
   ```

2. Add a free FIRMS key, needed only for NOAA-21, 2026 data and on-demand areas. Get one at https://firms.modaps.eosdis.nasa.gov/api/map_key/, copy `.env.example` to `.env`, and set `FIRMS_MAP_KEY`.

3. Download the data. This is resumable and checksummed, and verified files are skipped on rerun.

   ```bash
   .venv/Scripts/python scripts/download_data.py --archive --boundaries
   ```

   ```bash
   .venv/Scripts/python scripts/download_data.py --api-full
   ```

4. Process, validate and precompute.

   ```bash
   .venv/Scripts/python scripts/run_pipeline.py all
   ```

   ```bash
   .venv/Scripts/python validation/run_validation.py
   ```

   ```bash
   .venv/Scripts/python scripts/run_eda.py
   ```

   ```bash
   .venv/Scripts/python -c "from backend.services import precompute; precompute.build()"
   ```

5. Build the web app and start the server, then open http://localhost:8000.

   ```bash
   cd frontend && npm install && npm run build && cd ..
   ```

   ```bash
   .venv/Scripts/python -m uvicorn backend.api.main:app --port 8000
   ```

For development, run `npm run dev` in `frontend/` (http://localhost:5173, with `/api` proxied to port 8000).

To run the tests (35 tests: parsers, grid, calibration, anomalies, windows, and the API against real data):

```bash
.venv/Scripts/python -m pytest tests -q
```

Shareable links:

| Link | Opens |
|---|---|
| `/?story=sherani-2022` | Sherani fire story |
| `/?story=punjab-seasons` | Punjab burning seasons story |
| `/?aoi=PAK-ADM1-5&date=2025-11-05` | Punjab on 5 Nov 2025 |
| `/?tab=method` | Method & validation page |

## Project structure

```
backend/
  ingestion/      downloader (resume, retries, checksums, manifest) and inventory
  processing/     normalizer (all FIRMS layouts), grid aggregation, persistent-source classes
  harmonization/  calibration (8-day windows, CV model selection), harmonized record
  analytics/      robust seasonal anomalies, critical burning windows
  services/       custom areas, story definitions, web precompute
  api/            FastAPI app (DuckDB over Parquet), also serves the built frontend
frontend/         React + Vite + TypeScript, MapLibre GL, Apache ECharts
validation/       validation experiments -> results.json
scripts/          download, pipeline, EDA, API probes
docs/             plan, amendments, EDA and validation reports, screenshots, demo script
tests/            pytest suites
data/             raw (unchanged NASA files), processed, metadata (manifest, inventory)
```

## Data sources and attribution

- NASA FIRMS: MODIS Collection 6.1 and VIIRS 375 m active fire products (S-NPP, NOAA-20, NOAA-21) — https://firms.modaps.eosdis.nasa.gov/
- NASA FIRMS missing-data table — https://firms.modaps.eosdis.nasa.gov/api/missing_data/
- geoBoundaries gbOpen, Pakistan ADM0–ADM2 (2019 edition, public domain) — https://www.geoboundaries.org/
- NASA GIBS / Worldview true-colour imagery (optional map layer)
- Basemap: Esri World Dark Gray Base (© Esri, HERE, Garmin, © OpenStreetMap contributors)

We acknowledge the use of data and imagery from NASA's Fire Information for Resource Management System (FIRMS), part of NASA's Earth Science Data and Information System (ESDIS).

## License

Code: MIT License, © 2026 Team FireSight (see [LICENSE](LICENSE)). NASA FIRMS data and geoBoundaries layers are not included in this repository and remain subject to their providers' terms.
