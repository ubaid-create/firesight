# FireSight — Plan Amendment 2 (2026-11-14, after Milestone 1)

Milestone 1 is accepted. This amendment adds requirements to the approved plan in `PROJECT_PLAN.md`; it does not repeat or replace completed work.

## 1. Verified API findings

Tested with the MAP_KEY stored in the local `.env` (the key is never logged or printed).

| Source | Available (data-availability endpoint) | Test request result |
|---|---|---|
| MODIS_SP | 2000-11-01 .. 2026-08-31 | 2026-03-01, 5 days: 540 rows, Terra+Aqua, 15 columns incl. `type` |
| VIIRS_SNPP_SP | 2012-01-20 .. 2026-07-31 | 3,035 rows |
| VIIRS_NOAA20_SP | 2018-04-01 .. 2026-07-31 | 2,378 rows |
| VIIRS_NOAA21_SP | 2023-03-01 .. 2026-07-31 | 2024-05-01, 5 days: 5,203 rows, `N21`, 15 columns incl. `type` |
| MODIS_NRT | 2026-09-01 .. 2026-11-14 | 1,609 rows, 14 columns, no `type` |
| VIIRS_SNPP_NRT | 2026-08-01 .. 2026-11-02 | 3,708 rows; last date 2026-11-02 |
| VIIRS_NOAA20_NRT | 2026-08-01 .. 2026-11-14 | 2,096 rows |
| VIIRS_NOAA21_NRT | 2024-01-17 .. 2026-11-14 | 2,762 rows, `N21`, version `2.0NRT` |

Row counts are for the Pakistan bounding box, which also covers parts of neighbouring countries. Rows are clipped to the ADM0 polygon during normalization.

Layout notes: API NRT files have 14 columns (they include `instrument`, unlike the open 24-hour files) and no `type`. API `acq_time` is not zero-padded (`709`), MODIS satellite is `Terra`/`Aqua`, VIIRS confidence is `l`/`n`/`h`.

**Route decision.** The authenticated Archive Download tool does offer NOAA-21 (1 March 2023 onward) but needs a manual login, a request form and an emailed link. The Area API returned valid NOAA-21 standard data on the first test and is automated and resumable, so the API is used: about 250 requests for NOAA-21 standard data, about 135 for 2026 standard data on the other platforms, and about 80 for the near-real-time gap (roughly 465 in total).

## 2. Methodology additions

1. **Multi-satellite observation bias (core).** Platforms are kept separate everywhere: Terra, Aqua, SNPP, NOAA20, NOAA21, plus the derived group MODIS (union of Terra and Aqua cells). Unique active 1 km cells are counted per platform per day; 8-day values are sums of daily cell counts ("cell-days"). Raw counts are never summed across platforms and never divided by the number of satellites. A "naive union" series is computed only to demonstrate the artificial increases it produces at each platform introduction.
2. **Observation timing.** Each detection keeps its UTC timestamp and gets local solar time = UTC + longitude/15 hours. EDA reports overpass-time distributions per platform and year, which also reveals orbit drift. Same-day detections are not assumed to be the same fire. Cross-sensor correspondence is reported as a statistic and as a per-cell "platforms that saw it" flag, with a time-difference condition for the Aqua / S-NPP pair.
3. **Observation opportunity.** FIRMS hotspot files contain no record of overpasses without detections, so true opportunity cannot be measured from them. What is measurable and reported: distinct overpass times with detections per platform-day, pixel-size (scan) distribution, and day/night split. This limit is stated on the method page.
4. **Continuity links, each with its own fit and held-out test.**

| Link | Train | Test | Used for |
|---|---|---|---|
| Terra → S-NPP | 2012–2021 | 2022–2025 | Nov 2000 – Jul 2002 |
| MODIS (Terra+Aqua) → S-NPP | 2012–2021 | 2022–2025 | Jul 2002 – Jan 2012 |
| Terra → MODIS (Terra+Aqua) | 2003–2014 | 2015–2025 | Diagnostic for the 2002 transition only |
| NOAA-20 → S-NPP | 2018–2022 | 2023–2025 | Secondary carrier after 2 Nov 2026; historical bridge |
| NOAA-21 → S-NPP | chosen from actual overlap | last part of overlap | Primary carrier after 2 Nov 2026, if validated |

   The direct Terra → S-NPP link is used for the Terra-only period instead of chaining two models, to avoid compounding error.
5. **Temporal resolution.** Calibration is fitted on 8-day windows by region. Two calendar measures are produced and labelled:
   - *8-day rolling harmonized activity*, the native calibration resolution;
   - *daily activity*, which for calibrated periods distributes the calibrated 8-day total across days in proportion to the observed daily values, and for the reference period is the observed S-NPP daily value.

   Daily agreement is tested separately and reported. Where it is poor, the calendar defaults to the 8-day measure.
6. **Persistent thermal sources.** Per 1 km cell: *known static* (FIRMS `type` 2 dominant, or types 1/3), *suspected persistent* (active in most years, spread over most calendar months, weak seasonality; thresholds reported and adjustable), *normal/seasonal*. Nothing is deleted. Filtering suspected sources is optional and off by default. Known static types are excluded from the default vegetation-fire view as already planned.

## 3. Data schema

**`data/processed/normalized/detections.parquet`** — one row per original detection

| Column | Notes |
|---|---|
| det_id | stable integer |
| lat, lon | original |
| ts_utc, date, acq_hhmm | UTC |
| local_solar_hour | UTC + lon/15 |
| platform | Terra, Aqua, SNPP, NOAA20, NOAA21 |
| instrument | MODIS, VIIRS |
| processing | SP, NRT |
| version | as delivered |
| brightness, brightness_2 | MODIS: band 21/22 and band 31; VIIRS: I-4 and I-5 |
| frp | MW, per sensor |
| conf_raw, conf_class | original string; low/nominal/high by sensor-specific rule |
| scan_km, track_km, daynight | original |
| det_type | 0–3, null when absent (NRT) |
| cell_x, cell_y | EPSG:6933, 1 km |
| adm1, adm2 | geoBoundaries unit index, -1 if outside |
| source_file, source_row | provenance |

Other tables:
- `gridded/cell_day.parquet` — cell × date × platform: detections, max FRP, default-filter flag, region ids.
- `gridded/cell_class.parquet` — cell: years active, months spread, type shares, persistence class.
- `harmonized/platform_daily.parquet` — AOI × date × platform: detections, active cells (1 km and 2 km), FRP statistics, confidence mix, day/night counts, unclassified count.
- `calibrated/calibration.json` — per link: model, parameters, training period, sample counts, residual quantiles.
- `harmonized/harmonized_daily.parquet` — AOI × date: harmonized 8-day rolling value with interval, daily value with interval, both indices, carrier platform, method, quality state, anomaly score and label, provisional flag.
- `harmonized/critical_windows.parquet`.
- `validation/results.json`, `docs/VALIDATION_REPORT.md`, `docs/EDA_REPORT.md`.

AOIs precomputed: Pakistan, 7 ADM1 units, 126 ADM2 units. Custom AOIs are computed on request from `cell_day`.

## 4. Existing scripts to modify
- `scripts/download_data.py`: planned API mode added (`--api-full`).
- `backend/config.py`: platform codes, calibration links and splits.
- `backend/ingestion/data_downloader.py`: no change needed.
- New modules: `backend/processing/` (normalizer, aggregate, quality_control), `backend/harmonization/` (calibration, harmonize), `backend/analytics/` (anomaly, critical_windows), `validation/run_validation.py`, `scripts/run_pipeline.py`, `scripts/run_eda.py`.

## 5. Revised Milestone 2 sequence, outputs and checks

| Stage | Output | Checks |
|---|---|---|
| 2.1 Normalize, grid, regions | detections.parquet | row count equals raw rows minus counted exclusions; no null timestamps; parser tests for every layout |
| 2.2 EDA and quality | EDA_REPORT.md | counts per platform/year, type, confidence, version, overpass times, pixel sizes, SP/NRT overlap |
| 2.3 Cell-day and persistence | cell_day, cell_class | unique (cell, date, platform); class counts reported |
| 2.4 Platform daily and 8-day metrics | platform_daily | country total equals a direct recount; MODIS group ≤ Terra + Aqua |
| 2.5 Calibration per link | calibration.json | model chosen by cross-validation inside training years only; test years untouched until final scoring |
| 2.6 Harmonized record and indices | harmonized_daily | reference period equals observed S-NPP; no negative values; missing is not zero |
| 2.7 Anomalies and windows | parquet tables | leap-year and zero-MAD tests |
| 2.8 Validation | results.json, VALIDATION_REPORT.md | experiments 1–6 with real numbers; geographic holdout if time allows |

## 6. Application additions (Milestones 3–4)

**Priority 2**
- Story Mode: Sherani chilgoza forest fire (May 2022); Punjab crop-residue burning seasons; one international case only if time and data allow.
- "Current vs historical median" card using like-for-like date ranges (for example 1–14 November against 1–14 November in earlier years), labelled provisional when it rests on near-real-time data.

**Priority 3**
- Persistent-source toggle.
- Palettes: Viridis (default), Cividis, YlOrRd.
- Filters: platform, day/night, per-sensor confidence, detection type.
- CSV export with uncertainty, quality state and calibration provenance.
- AOI coverage states: preloaded Pakistan · other processed datasets · on-demand API · not acquired.
