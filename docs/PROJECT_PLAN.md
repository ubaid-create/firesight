# FireSight — Project Execution Plan

**FireSight: Harmonized MODIS and VIIRS Satellite Fire Intelligence Platform**
*One Earth. Multiple Satellites. One Harmonized Fire History.*

Plan date: 2026-11-14 (07:10 UTC). Status: **awaiting approval**. Nothing has been bulk-downloaded and no application code exists.

Legend used throughout: **[V]** verified by me today with a real request · **[D]** read from official documentation only · **[U]** stated by you or by third parties, not verified by me.

---

## Approved amendments (2026-11-14)

The plan was approved with the following corrections, which override the sections below where they differ.

1. **Temporal resolution.** Original daily observations are preserved. Sensor relationships are estimated on 8-day aggregates. An 8-day estimate is never presented as an exact daily count. The calendar keeps daily navigation with a labelled daily activity index and uncertainty; where daily calibration is not reliable enough, it shows an explicitly labelled 8-day rolling harmonized score. Tooltips and the method page state which resolution is shown.
2. **Post-S-NPP continuity.** NOAA-21 is the primary and NOAA-20 the secondary platform after S-NPP (per NOAA's recommendation, as stated by the team). NOAA-20 is the historical calibration bridge because of its longer overlap. NOAA-21 availability (`VIIRS_NOAA21_SP`, `VIIRS_NOAA21_NRT`) is queried, the authenticated Archive Download route is investigated before using many Area API calls, and a NOAA-21 → S-NPP calibration is attempted on the real overlap. If it cannot be calibrated in time, NOAA-21 is displayed separately, labelled uncalibrated/provisional, and is not included in the harmonized record.
3. **Validation splits.** MODIS → S-NPP: train 2012–2021, test 2022–2025. NOAA-20 → S-NPP: train 2018–2022, test 2023–2025. NOAA-21 → S-NPP: split chosen from the actual overlap and sample counts. The July 2002 Terra/Aqua transition is investigated. Test data are never used for tuning. No smoothing to hide transitions.
4. **Acquisition.** Archive: MODIS 2000–2025, S-NPP 2012–2025, NOAA-20 2018–2025. 2026: standard data to its maximum available date, NRT for the remaining gap, latest 30–60 days first.
5. **Permissions granted.** venv, packages, React/Vite, npm install, git init, directory structure, `.env.example`, `.gitignore`, scripts, approved downloads. No push to a remote and no public deployment without separate approval.
6. **Non-negotiable features.** Harmonization; calendar; Pakistan AOI map; before/after comparison; seasonal trends; anomaly detection; critical windows; platform comparisons; coverage and uncertainty indicators; methodology with actual validation results.

---

## A. Project assessment

### A.1 The challenge as I understand it
MODIS (1 km, Terra from Nov 2000, Aqua from Jul 2002) and VIIRS (375 m, S-NPP from Jan 2012, later NOAA-20 and NOAA-21) record active-fire hotspots with different resolution, sensitivity, overpass times and confidence schemes. Counting them together produces step changes in the record that are caused by satellites, not by fire. The task is to turn these records into one consistent burning-activity history and present it as a calendar a user can explore for a chosen region.

### A.2 What I could not verify
The official challenge page (`spaceappschallenge.org/2026/challenges/modis-and-viirs-hot-spots/`) **does not load from this computer**: every attempt fails the TLS certificate check, from the terminal and from the built-in browser. I have not bypassed that check. My reading of the requirements therefore rests on **[U]** sources: your specification, the earlier AI summary, and public team repositories. The three user needs they agree on are:

1. examine historical fire patterns for a selected region;
2. identify unusual burning activity;
3. find critical periods when burning is historically more likely;

delivered as a web application built around a burning-activity calendar. The judging criteria (Impact, Creativity, Validity, Relevance, Presentation) and the deadline (Nov 15, 23:59 local) are also **[U]**. Please paste the official text so I can check the plan against it (see section H).

### A.3 Recommended solution
A local-first web application whose scientific core is a **reference-scale harmonization**: every platform's daily activity is measured on a common 1 km equal-area grid, then expressed on one reference scale (VIIRS S-NPP) using calibration fitted only on real overlap periods and tested on held-out years. The calendar, anomaly detection and critical windows are all computed from that single harmonized series, and every value carries its sources and uncertainty.

### A.4 Differentiators
- All platform transitions handled, not just 2012: Terra-only → Terra+Aqua (2002), MODIS → S-NPP (2012), S-NPP → NOAA-20 (needed now that S-NPP has ended).
- A before/after chart with real held-out error numbers, rather than a smoothed line.
- "No detections" is never shown as "no fire" and never confused with "no data".
- Fully reproducible from the original NASA files via a checksummed manifest.

### A.5 Where I recommend departing from the specification
| Spec item | Issue | Recommendation |
|---|---|---|
| Daily "S-NPP-equivalent" value for 2000–2011 | A single MODIS day cannot support a precise VIIRS-equivalent number; daily cross-sensor scatter is large | Fit calibration on aggregated units (8-day × sub-region), apply it to daily values, and show an uncertainty band. The daily calendar shows the index and band, not a false-precision count |
| Reference scale = S-NPP | S-NPP has stopped delivering data, so the reference cannot extend forward by itself | Keep S-NPP as the reference scale for history; calibrate NOAA-20 to it on 2018–2025 overlap and use NOAA-20 as the carrier from 2026 |
| Land-cover-dependent calibration | Needs another dataset and download | Out of scope; use month and sub-region instead |
| MCD64A1 / VNP64A1 comparison | Different format (HDF tiles), Earthdata login, hours of work | Stretch only |
| NOAA-21 calibration (Experiment 5) | Depends on MAP_KEY and on how much standard-quality data exists | Do it if the key arrives early; otherwise report as not evaluated |
| Footprint-based matching | Full footprint geometry is costly | Centroid gridding as the documented baseline, plus a sensitivity test that excludes wide off-nadir pixels |
| All 9 modules, 7 experiments, full test suite | Roughly 36 hours remain | Tiered scope in section G; core first, with an explicit cut order |

---

## B. Environment assessment (all [V])

| Check | Result |
|---|---|
| `D:\firesight` access, read/write | Yes |
| Existing contents | Only `data\raw\nrt_7d\` (empty; I created it earlier and the downloads into it did not complete) and this plan |
| PowerShell and Bash commands | Yes |
| Python / pip | 3.12.0 / 26.2.1 |
| Node.js / npm | 24.19.0 / 11.17.0 |
| Git | 2.55.0; folder is not yet a repository |
| Python packages | **None of the required ones are installed** (pandas, numpy, duckdb, pyarrow, geopandas, shapely, pyproj, scipy, scikit-learn, requests, python-dotenv, fastapi, uvicorn, pytest) |
| Disk | 148 GB free on D: |
| Memory / CPU | 15.9 GB total, 6.4 GB free; Intel i5-8350U |
| Internet from terminal | Yes, but **unstable**: roughly one request in four dropped during testing and needed a retry |
| NASA FIRMS reachable | Yes |
| Can download NASA files directly | Yes (partial reads of real files succeeded) |
| Official challenge site | **No** — TLS certificate error |

Consequences: the downloader must retry and resume (already in your spec); I will create a `.venv` and install packages after approval; the certificate problem may also affect your project submission from this machine, so test the submission page early or use another device.

---

## C. Verified data-source matrix

| # | Source | URL | Provides | Period | Quality | Format | Auth | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | FIRMS country archive catalogue | `firms.modaps.eosdis.nasa.gov/data/country/yearly_summary_files.txt` | List of every yearly country file with size and update time | — | — | CSV text | None | **[V]** 200, 10,144 entries |
| 2 | MODIS C6.1 country/year | `…/data/country/modis/{year}/modis_{year}_Pakistan.csv` | Terra + Aqua detections | 2000–2025 (26 files, 18.2 MB for Pakistan) | Standard | CSV | None | **[V]** header and rows read for 2000, 2023, 2025 |
| 3 | VIIRS S-NPP country/year | `…/data/country/viirs-snpp/{year}/viirs-snpp_{year}_Pakistan.csv` | S-NPP 375 m | 2012–2025 (14 files, 64.8 MB) | Standard | CSV | None | **[V]** 2023 and 2025 read |
| 4 | VIIRS NOAA-20 country/year | `…/data/country/viirs-jpss1/{year}/viirs-jpss1_{year}_Pakistan.csv` | NOAA-20 375 m | 2018–2025 (8 files, 39.3 MB) | Standard | CSV | None | **[V]** 2023 read. Product code is `viirs-jpss1`, not "noaa20" |
| 5 | VIIRS NOAA-21 country/year | `…/viirs-jpss2/…`, `…/viirs-noaa21/…` | — | — | — | — | — | **[V] does not exist**: 404 JSON for both names, and absent from the catalogue |
| 6 | FIRMS Area API | `…/api/area/csv/{MAP_KEY}/{SOURCE}/{W,S,E,N}/{1-5}/{DATE}` | Any source by bounding box | Per data-availability endpoint | SP and NRT | CSV | MAP_KEY | **[D]** sources listed: MODIS_NRT, MODIS_SP, VIIRS_SNPP_NRT/SP, VIIRS_NOAA20_NRT/SP, VIIRS_NOAA21_NRT/SP, LANDSAT_NRT. 1–5 days per call; 5,000 transactions per 10 min. **Not tested (no key)** |
| 7 | FIRMS data availability | `…/api/data_availability/csv/{MAP_KEY}/all` | min/max date per source | — | — | CSV | MAP_KEY | **[D]** not tested |
| 8 | FIRMS missing data | `…/api/missing_data/` | Dates with missing satellite data | — | — | — | Likely MAP_KEY | Page reached but content not readable without a key; **not verified** |
| 9 | FIRMS open 24h/7d files | `…/data/active_fire/{modis-c6.1,noaa-20-viirs-c2,noaa-21-viirs-c2,suomi-npp-viirs-c2}/csv/…` | Latest detections by region | Last 24h–7d | NRT | CSV | None | **[V]** MODIS, NOAA-20, NOAA-21 return rows dated 2026-11-13; **S-NPP file returns a header and no rows** |
| 10 | FIRMS archive download tool | `…/download/` | Custom historical requests | Full archive | SP | CSV/SHP/JSON | Earthdata login or emailed code | **[D]** not needed if 6 works |
| 11 | MAP_KEY registration | `…/api/map_key/` | Free API key by email | — | — | — | Email | **[D]** |
| 12 | geoBoundaries PAK ADM1 | `geoboundaries.org/api/current/gbOpen/PAK/ADM1/` | Provinces/territories | 2019 | — | GeoJSON | None | **[V]** 7 units, Public Domain, build Dec 12 2023 |
| 13 | geoBoundaries PAK ADM2 | `…/PAK/ADM2/` | Districts | 2019 | — | GeoJSON | None | **[V]** 126 units, Public Domain |
| 14 | geoBoundaries PAK ADM0 | `…/PAK/ADM0/` | Country outline | — | — | GeoJSON | None | Request dropped; **not verified** |
| 15 | Official challenge page | `spaceappschallenge.org/2026/challenges/modis-and-viirs-hot-spots/` | Requirements | — | — | — | None | **Not reachable** (certificate error) |

### Field-level findings from the real files [V]
- **Archive (standard) files** share 15 columns and all include `type`. MODIS: `brightness`, `bright_t31`, numeric `confidence`, `satellite` = `Terra`/`Aqua`. VIIRS: `bright_ti4`, `bright_ti5`, `confidence` = `l`/`n`/`h`, `satellite` = `N` (S-NPP) or `N20`.
- **NRT files differ**: 13 columns, **no `instrument` and no `type`**; MODIS `satellite` = `A`/`T`; VIIRS `confidence` = `low`/`nominal`/`high`; `version` = `6.1NRT` / `2.0NRT`. The normalizer needs separate parsers for archive and NRT, and NRT rows will carry "type unknown".
- **Version varies inside MODIS**: `6.2` in the 2000 file, `61.03` in 2023 and 2025. I will record it per row and report the distribution before deciding whether it matters.
- `type` values 1 and 2 already appear in the samples (a static source in the first row of MODIS 2000), so the vegetation-fire filter has a real effect.
- MODIS `scan` reached 3.47 km in an NRT sample row, confirming that off-nadir pixels are several times larger than nominal.

### Discrepancies and open points
- S-NPP ending on 2 Nov 2026 is **[U]**. The empty S-NPP 24h file is consistent with it but is not official confirmation.
- NOAA-21 start date and how much of it is standard quality are unknown until the data-availability endpoint is queried with a key.
- 2026 is not in the country archive for any product; it must come through the API.

---

## D. Dataset acquisition plan

### D.1 Files (Pakistan)
| Set | Files | Size | Route | Needs |
|---|---|---|---|---|
| MODIS 2000–2025 | 26 | 18.2 MB | Country archive | Nothing |
| VIIRS S-NPP 2012–2025 | 14 | 64.8 MB | Country archive | Nothing |
| VIIRS NOAA-20 2018–2025 | 8 | 39.3 MB | Country archive | Nothing |
| Boundaries ADM0/1/2 | 3 | a few MB (unverified) | geoBoundaries API → GeoJSON | Nothing |
| 2026 to date: MODIS, S-NPP, NOAA-20 | — | small | Area API, bbox `60.5,23.5,77.8,37.1` | MAP_KEY |
| NOAA-21, full available period | — | unknown | Area API | MAP_KEY |

Total without a key: **48 files, about 122 MB**. Nothing else will be downloaded.

### D.2 API request estimate
At 5 days per call, 2026 to date is about 64 calls per source. NOAA-21 from an assumed early-2024 start is about 210 calls. Roughly 400–470 calls in total, well inside 5,000 per 10 minutes even if a country-sized box counts as several transactions each. The real start dates come from the data-availability response, not from this estimate. Standard and NRT are fetched as separate sources and stored separately.

### D.3 Order
1. One sample per product (MODIS 2023, S-NPP 2023, NOAA-20 2023), fully validated: status, content type, header, row count, date range, bounding box, duplicates, nulls, satellite values.
2. If all pass, the remaining 45 archive files and the boundaries.
3. When the key exists: data availability → 2026 and NOAA-21.

### D.4 Downloader behaviour
`.part` temp files renamed only after a complete download; size checked against the catalogue; rejects HTML/JSON bodies and header-only files; retry with exponential backoff; skips files already validated; SHA-256 per file; manifest and `data/metadata/data_inventory.csv` with the columns you listed; the key is read from `.env` and never printed or logged. Raw files are never modified.

### D.5 Storage
The directory layout in your section 8 is used as written, with two small changes: `data/raw/nrt/` for provisional data (kept apart from standard files) and `data/raw/viirs_noaa20/` holding the `viirs-jpss1` files. The empty `data/raw/nrt_7d/` folder I created earlier will be removed.

### D.6 Manual steps for you
1. Open https://firms.modaps.eosdis.nasa.gov/api/map_key/, enter your email, and wait for the key.
2. After I create `.env.example` and `.gitignore`, create `D:\firesight\.env` containing `FIRMS_MAP_KEY=<your key>`. Do not paste the key into chat.

The project can start and reach a working demo on 2000–2025 without the key.

---

## E. Scientific methodology

### E.1 Normalization
Separate parsers for MODIS archive, VIIRS archive, MODIS NRT and VIIRS NRT feed one schema: coordinates, UTC timestamp (from `acq_date` + `acq_time`), `satellite` (Terra, Aqua, SNPP, NOAA20, NOAA21), `instrument`, `brightness` and `secondary_brightness` (with their original channel names recorded), `frp`, `confidence_raw`, `confidence_class`, `scan_km`, `track_km`, `daynight`, `detection_type` (null when absent), `processing` (SP/NRT), `version`, `source_file`, `source_row`. Raw values are never overwritten.

**Confidence policy.** Classes are low / nominal / high. VIIRS maps directly. MODIS uses the documented FIRMS convention of <30 low, 30–80 nominal, >80 high **[D — to be re-checked against the MODIS user guide before use]**. Default analysis keeps nominal and high; a sensitivity run includes low. The two scales are never treated as numerically equal.

**Type policy.** Default view: `type = 0` where type exists. Types 1–3 are kept and viewable. Rows with no type (NRT) are kept, flagged "unclassified", and additionally flagged if they fall in a grid cell that was repeatedly type 2 in the standard archive.

**Duplicates.** Exact duplicate rows are counted and reported, then removed in the normalized layer only.

### E.2 Common grid
EPSG:6933 (global equal-area), 1 km cells, integer cell ID from projected coordinates. Per sensor and day, a cell is active once, however many pixels fall in it. This removes the "one MODIS pixel = several VIIRS pixels" effect at the counting stage. It does **not** equalize detection sensitivity or overpass frequency; calibration handles that, and the method page says so. Gridding is by pixel centre; a 2 km grid and an "exclude wide off-nadir pixels" run are the sensitivity tests.

### E.3 Daily metrics per platform
Detections, unique active cells, active-cell density (cells ÷ AOI km²), FRP mean / max / quartiles, confidence mix, day/night split, unclassified count, processing version. Stored per platform; nothing is summed across platforms.

### E.4 Time handling
Daily values are kept, but calibration is fitted on **8-day windows** because Terra (~10:30 and 22:30 local), Aqua and S-NPP (~13:30 and 01:30), and NOAA-20/21 (same orbit as S-NPP, offset in time) see different moments of a fire and different swaths each day. Day and night are calibrated separately where sample size allows. A same-day co-occurrence is never claimed to be the same fire.

### E.5 Calibration and continuity
Reference scale: **VIIRS S-NPP active-cell density**.

| Link | Fitted on | Used for |
|---|---|---|
| Terra-only → Terra+Aqua | Aug 2002 onward, by recomputing the series with Aqua removed | Nov 2000 – Jul 2002 |
| MODIS (Terra+Aqua) → S-NPP | 2012–2021 | 2002 – 2011, and as an independent check afterwards |
| NOAA-20 → S-NPP | 2018–2021 (test 2022–2025) | 2026 onward |
| NOAA-21 → S-NPP | whatever overlap exists | Reported only, if data allow |

Unit of fitting: 8-day window × sub-region (ADM1, or a coarse grid block for custom AOIs) × calendar month group. Methods compared, simplest first:
1. single ratio (baseline);
2. month-specific robust regression in log space (Theil–Sen or Huber);
3. month-specific quantile mapping.

Model choice uses cross-validation **inside the training years only**. If a month or region has too few paired non-zero windows, it falls back to the pooled model and the output is flagged "low calibration support". Zeros are handled explicitly (a zero-MODIS window is not multiplied into a zero estimate with false certainty; it receives the empirical S-NPP distribution observed for zero-MODIS windows).

**Uncertainty.** Prediction intervals from training residuals, by month. Their coverage is checked on the test years.

**Harmonized series.**
- Nov 2000 – Jul 2002: calibrated Terra (two chained links, widest uncertainty)
- Aug 2002 – Jan 2012: calibrated MODIS
- Jan 2012 – 2025: S-NPP observed (reference)
- 2026 onward: calibrated NOAA-20, flagged provisional where NRT

The calibrated-MODIS series is also kept for 2012–2025 so users can see estimate and reference side by side. Real trends are untouched: calibration relationships are fixed in time, so a genuine increase in fire shows in both.

### E.6 Burning-activity index (0–100)
Percentile of the harmonized daily density within that AOI's full history, computed over non-zero days, with 0 reserved for "no detections recorded". Labels: 0–20 very low, 21–40 low, 41–60 moderate, 61–80 elevated, 81–100 high (interface labels, not NASA thresholds). The underlying density and the uncertainty band are always shown beside it. An AOI with too few active days returns "insufficient history" instead of a score. FRP stays separate and per sensor.

### E.7 Anomalies
`Z = (x − median) / (1.4826 × MAD)` against the same day-of-year ±7 days in all other years. Feb 29 is folded into Feb 28 for baselines. If MAD is zero or fewer than a minimum number of baseline values exist, the detector falls back to a percentile rank or returns "insufficient baseline". Labels (unusually low / normal / elevated / highly unusual) use thresholds set from the observed Z distribution and documented.

### E.8 Critical burning windows
For each week of the year: the share of years in which weekly activity exceeded that AOI's 75th-percentile weekly level, plus the median and range. Adjacent qualifying weeks merge into a window. Output wording follows the pattern "elevated in N of M years with sufficient data".

### E.9 Coverage and data quality
Each AOI-day gets one of: detections recorded · no detections recorded · source not yet operating · known missing data (from the missing-data endpoint, if it works with the key) · provisional (NRT). The calendar draws these differently; missing is never drawn as zero. Pixel-level cloud or swath coverage is **not** available from these products and the app says so.

### E.10 Validation
All numbers will be computed, none assumed. S-NPP is a reference, not ground truth; results are described as cross-sensor agreement.

| # | Experiment | Tier |
|---|---|---|
| 1 | Raw MODIS vs raw S-NPP (ratio by month and year) | Core |
| 2 | Before vs after calibration: step size at 2012 | Core |
| 3 | Held-out years: fit 2012–2021, test 2022–2025 (MAE, RMSE, bias, Spearman, interval coverage) | Core |
| 4 | Terra-only vs Terra+Aqua | Core (cheap: same code) |
| 5a | NOAA-20 vs S-NPP | Core |
| 5b | NOAA-21 vs S-NPP | Stretch (needs key and data) |
| 6 | 1 km vs 2 km grid | Core |
| 7 | Geographic holdout: fit on some provinces, test on others | Stretch |
| 8 | Burned-area comparison (MCD64A1) | Not planned |

---

## F. Technical implementation

**Stack.** Python 3.13 in `.venv` (moved from 3.12 on 2026-11-14 to match the team's contributors): pandas, numpy, pyarrow, duckdb, pyproj, shapely, scipy, scikit-learn, requests, python-dotenv, fastapi, uvicorn, pytest. geopandas only if shapely + pyproj prove insufficient. Frontend: React + Vite + TypeScript, MapLibre GL JS, ECharts. Storage: Parquet queried with DuckDB. No external database, no cloud services.

**Precompute, then serve.** The pipeline writes normalized detections, a per-platform cell-day table, calibration parameters, and daily harmonized series for the country, each province and each district. Custom polygons are computed on request from the cell-day table (cells are small enough for this to be fast).

**Backend modules.** As in your section 17, with `normalizer` + `quality_control` kept separate and `harmonization` owning the series assembly. One CLI entry point (`scripts/run_pipeline.py`) runs any stage and is safe to rerun.

**API.**
| Endpoint | Returns |
|---|---|
| `GET /api/meta` | sources, date coverage, pipeline and calibration version |
| `GET /api/aois`, `GET /api/aois/{id}` | AOI list, geometry |
| `POST /api/aoi/custom` | registers a drawn polygon, returns an AOI id |
| `GET /api/calendar?aoi=&from=&to=` | day × year matrix: index, density, band, quality state, anomaly label |
| `GET /api/day?aoi=&date=` | per-platform metrics, FRP stats, anomaly detail, sources |
| `GET /api/hotspots?aoi=&date=&platform=&…` | original detections as GeoJSON |
| `GET /api/series?aoi=&freq=` | per-platform and harmonized series, raw and calibrated |
| `GET /api/anomalies?aoi=` | ranked unusual dates |
| `GET /api/windows?aoi=` | critical burning windows |
| `GET /api/validation` | experiment results and calibration parameters |
| `GET /api/export?aoi=&…` | CSV |

**Frontend.** One dashboard and one method page.
- Dashboard: AOI picker (country / province / district / draw), overview strip, calendar heatmap (day of year × year) as the largest element, map with platform layers and filters, day detail panel, sensor comparison with transition markers and a before/after toggle, trends, anomaly list, critical windows.
- Method and validation page: sources, timeline, pipeline diagram, calibration, index, limits, real validation tables.
- Dark, restrained geospatial style; one consistent colour scale for the index; distinct hatching for missing/provisional days.

**Tests.** pytest for parsing (all four file kinds), timestamps, confidence and type policy, grid assignment, aggregation, calibration round-trip, leap-year handling, anomaly edge cases, missing-versus-zero, and API responses; one end-to-end check that the API's calendar values equal the pipeline output.

**Security and repo hygiene.** `.env` git-ignored; key used server-side only; `data/raw` and `data/processed` git-ignored; `git init` locally, publishing to GitHub left to you.

---

## G. Development roadmap

Time available: about 36 hours if the deadline is Nov 15, 23:59 local **[U]**. Estimates are my working time; they exclude your review time and download waits.

| Phase | Work | Depends on | Estimate |
|---|---|---|---|
| 1 | venv, scaffolding, downloader, samples, bulk archive, boundaries, inventory | Approval | 1.5 h |
| 2 | EDA: counts by year/platform/month, confidence, FRP, type, version, transitions; saved charts and notes | 1 | 1 h |
| 3 | Normalize, QC, grid, daily metrics, calibration, harmonized series, index, anomalies, windows | 2 | 4.5 h |
| 4 | Validation experiments (core tier) and report | 3 | 2 h |
| 5 | FastAPI endpoints and tests | 3 | 2 h |
| 6 | Frontend: calendar → map → day panel → comparison → trends/anomalies/windows → method page | 5 | 6 h |
| 7 | Integration testing and fixes | 6 | 2 h |
| 8 | README, screenshots, diagrams, demo script, pitch notes | 7 | 2 h |
| — | 2026 and NOAA-21 via API, folded in whenever the key arrives | MAP_KEY | 1 h |

About 22 hours of work, leaving buffer. Each phase ends with a short report of real results before the next begins.

**Cut order if time runs short** (first to go at the top): geographic holdout · NOAA-21 calibration · custom polygon drawing · CSV export and report · trends module detail · annual calendar alternative view. The calendar, calibration with held-out validation, map, sensor comparison and method page are not cut.

**Risks and fallbacks.**
| Risk | Fallback |
|---|---|
| Unstable connection | Resumable downloader; only 122 MB needed |
| Calibration is weak at district scale (few fires) | Fit at province/country level, apply downward, flag low support; districts with too little history show "insufficient data" |
| Monthly models overfit | Pooled robust ratio with seasonal term; choice made on training-period cross-validation |
| No MAP_KEY in time | Ship 2000–2025 standard data; label 2026 as not included; open NRT 7-day files give a "latest week" view without a key |
| NOAA-21 standard data sparse | Show NOAA-21 as an observed layer only, not calibrated |
| Official requirements differ from my assumptions | Re-check as soon as you paste the page text |
| Certificate problem blocks submission from this PC | Submit from another device or network |
| Laptop performance | Pakistan data is small; everything is precomputed |

**Expected deliverables.** The 18 items in your section 21, with these qualifications: item 7 covers the three core calibration links; item 15 contains the core experiments; public deployment is not included.

---

## H. Approval checklist

Needed from you:
1. **Approve this plan**, or tell me what to change. In particular confirm the departures in A.5 and the tiering in E.10 and G.
2. **Paste the official challenge text** (I cannot open the page from this machine), and confirm the submission deadline and required submission items.
3. **Request a FIRMS MAP_KEY** and put it in `D:\firesight\.env` once I have created `.env.example`. Not blocking.
4. Confirm it is fine for me to create a Python virtual environment, install the listed packages, run `npm install` for the frontend, and `git init` the folder.

On approval I am ready to download the three sample files, validate them, and then proceed through Phase 1.
