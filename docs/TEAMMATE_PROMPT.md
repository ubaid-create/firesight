# FireSight: full project briefing for a teammate's Claude session

Copy everything below the line into the other chat as the first message.

---

You are helping a member of **Team FireSight** with our NASA Space Apps Challenge 2026 project. I have cloned the repository and have **Python 3.13** and Node.js installed. I need you to help me run, test and (carefully) modify the project, and to build our **presentation (max 7 slides) and the spoken presentation script**. Read this whole briefing before doing anything.

## 1. Links

| What | Link |
|---|---|
| Our repository | https://github.com/ubaid-create/firesight |
| Challenge: Harmonization of MODIS and VIIRS Hot Spots | https://www.spaceappschallenge.org/2026/challenges/modis-and-viirs-hot-spots/ |
| Judging & Awards Guide | https://www.spaceappschallenge.org/resources/judging-awards-guide/ |
| NASA FIRMS (data source) | https://firms.modaps.eosdis.nasa.gov/ |
| Free FIRMS MAP_KEY | https://firms.modaps.eosdis.nasa.gov/api/map_key/ |
| geoBoundaries (district/province borders) | https://www.geoboundaries.org/ |

## 2. Submission rules that matter right now (from the Judging & Awards Guide)

- **Deadline: Sunday 15 November 2026, 11:59 p.m. local time** of our Local Event (Universal Event: Team Owner's local time).
- The demo must be **either a slide presentation of at most 7 slides (including title and intro slides) or a video of at most 30 seconds**. A video in another language needs English subtitles. Everything on the submission page must be in English.
- All team members must be registered for the same event and appear on the team's Members tab; 1–6 members (Universal Event: at least 2).
- All external resources (code, text, images, even open-source ones) must be listed in the **References** field. Do not use copyrighted images or music without permission.
- Judges score 1–5 on five criteria:
  - **Impact**: how significant the problem is and how many people benefit.
  - **Creativity**: originality, a fresh approach or a meaningful improvement.
  - **Validity**: scientifically sound, technically feasible, usable, works.
  - **Relevance**: directly addresses the challenge; NASA data is the core, not decoration.
  - **Presentation**: clear, well-structured, engaging storytelling. The guide says to give this "equal attention".
- Global awards we fit best: **Best Use of Science**, **Best Use of Data**, **Local Impact Award** (Pakistan), **Best Storytelling**.

## 3. What the challenge asks for (summary of the challenge page)

Satellites have tracked active-fire hotspots for over 20 years, but the record is split between MODIS (Terra, Aqua; 1 km, being retired) and VIIRS (S-NPP, NOAA-20, NOAA-21; 375 m), which cannot be compared directly. Build a **web app with a harmonized burning-activity calendar** for a selected area of interest, so emergency managers, scientists and land managers can see historical patterns, unusual conditions and critical periods. Two parts: (1) harmonize MODIS and VIIRS so the sensor of origin no longer matters; (2) a web app where the user selects a region and date range and downloads analytics and visualizations. Suggested: compare the current month with the historical median; accessible colour ramps; draw an area or enter lat/lon; anomalies vs multi-year averages; number of fires detected; a downloadable CSV.

**FireSight covers every one of these points** (see section 5).

## 4. The problem we solved, in one paragraph

NASA FIRMS has five satellites with different pixel sizes and overpass times. Merging their detections naively creates artificial jumps every time a satellite is added: in Pakistan's FIRMS data the naive union **rises 5.5× when S-NPP arrives in 2012**, while MODIS alone rises only **1.13×**. That jump is the satellites, not more burning. FireSight turns the five records into **one consistent burning-activity history for Pakistan from November 2000 to the latest available day (13 Nov 2026)**, and shows it as an interactive burning calendar with maps, anomalies, critical windows and validation.
## 5. Features (all built and tested)

| Feature | What it does | Challenge point |
|---|---|---|
| Burning activity calendar | Day-of-year × year heatmap of harmonized 8-day activity 2000–2026, or a single-year calendar. Tooltips show index, 80% interval, method (observed/reconstructed), anomaly, data quality. Click a day → map and day panel update. Raw daily mode for any single platform. | Calendar, colour ramps |
| Fire map (MapLibre) | Detections from all 5 platforms; filters: platform, day/night, sensor-specific confidence, detection type, persistent sources. Activity-density grid, harmonized index by district/province, NASA GIBS true-colour layer, click-through details (source file and row). | Map, number of fires |
| Area selection | Pakistan, 7 provinces/territories, 126 districts, "Draw area" polygons, coordinate box (W,S,E,N). Outside Pakistan: "historical data not acquired", with an on-demand fetch of recent raw FIRMS detections; Pakistan's calibration is never applied there. | Draw AOI / lat-lon |
| Now vs historical median | Last 7/14/30 days vs the same dates in every year, like for like; also vs observed S-NPP years only. | Current vs median |
| Sensor harmonization charts | Naive union vs raw MODIS vs raw S-NPP vs harmonized, with transitions marked; each platform's own series; calibration check on overlap. | Part 1 of the challenge |
| Historical intelligence | Seasonal pattern; **critical burning windows** (weeks elevated in ≥50% of years); latest 14 days vs every year; ranked unusual episodes. | Critical periods, anomalies |
| Data quality | Reliability rating per area; provisional flag for near-real-time data; FIRMS missing-data days; "no detections" shown separately from "no satellite delivering". | Validity |
| Fire stories | Guided stories on the live app: **Sherani chilgoza pine forest fire (May 2022)** and **Punjab's two burning seasons** (spring and autumn bands whose timing coincides with the wheat (Apr–May) and rice (Oct–Nov) harvests; the link to crop-residue burning is an interpretation of the timing, not something the satellite data prove). | Storytelling |
| Export | Harmonized CSV (per-platform contributions, uncertainty, method, anomaly, calibration version) and raw detections CSV (source file and row). | CSV download |
| Accessibility | Viridis (default), Cividis (colour-vision safe), YlOrRd palettes; works on phones. | Accessible ramps |
| Method & validation page | Live validation tables and the full limitations list inside the app. | Validity |

Shareable URLs: `/?story=sherani-2022`, `/?story=punjab-seasons`, `/?aoi=PAK-ADM1-5&date=2025-11-05` (Punjab), `/?tab=method`.

## 6. How the harmonization works, and why each choice was made

1. **Raw NASA data, never altered.** FIRMS country archive (MODIS C6.1 2000–2025, VIIRS S-NPP 2012–2025, NOAA-20 2018–2025; no key needed) plus the FIRMS Area API (NOAA-21 standard data, 2026 standard data, and near-real-time data for the most recent days; needs a MAP_KEY). Every file is SHA-256 checksummed in `data/metadata/manifest.json`. *Why:* traceability; every number can be traced back to a NASA file and row. 1,871,495 detections kept.
2. **Normalization** of all FIRMS file layouts (archive 15 columns, API standard, API NRT without `type`) into one schema, keeping original confidence, brightness, pixel size, version, source file and row; UTC timestamp and local solar time. *Why:* the sensors' confidence scales are not equivalent, so we never mix them, and local solar time reveals overpass differences and Terra's orbit drift.
3. **Common 1 km equal-area grid (EPSG:6933).** For each platform and day, an active cell counts once. Platforms are never summed. *Why:* VIIRS's 375 m pixels produce several detections for one fire that MODIS sees as one; counting unique 1 km cells removes most of the pixel-size effect, and equal-area cells make areas comparable.
4. **Calibration on 8-day windows per province**, mapping each platform onto the **VIIRS S-NPP scale** (the reference, because it has the longest VIIRS record and overlaps every other platform). Candidate models: ratio, monthly ratio, regional ratio, region × season ratio, log-linear by month, scaled log-linear. The model per link is chosen by blocked-year cross-validation inside the training years, requiring cross-validated total bias ≤5%. 80% prediction intervals from log-residual quantiles. *Why 8-day windows:* single days are too noisy (clouds, overpass gaps); 8-day windows give stable relationships while still allowing daily navigation. *Why held-out years:* to prove the calibration works on years it never saw.

   | Link | Train | Held-out test |
   |---|---|---|
   | MODIS → S-NPP | 2012–2021 | 2022–2025 |
   | NOAA-20 → S-NPP | 2018–2022 | 2023–2025 |
   | NOAA-21 → S-NPP | Mar 2023–2024 | 2025 – Jul 2026 |
   | Terra → S-NPP (for 2000–2002) | 2012–2021 | 2022–2025 |

5. **One continuous record (carrier plan):** Nov 2000 – Jul 2002 calibrated Terra → Jul 2002 – Jan 2012 calibrated MODIS (Terra + Aqua) → Jan 2012 – 2 Nov 2026 observed S-NPP → from 3 Nov 2026 calibrated NOAA-21 (S-NPP data in FIRMS end on 2 Nov 2026; NOAA-21 passed the held-out bias test). Provinces are calibrated directly; the country is the sum of provinces; districts receive shares of their province. *Why:* one sensor at a time on one scale means no artificial jumps; summing provinces keeps the levels consistent.
6. **Activity index 0–100**: percentile within the area's own history (0 = no detections recorded). **Anomalies**: robust seasonal z = (x − median) / (1.4826 × MAD) against the same dates ±7 days in other years (min. 5 years; ≥2 elevated, ≥3.5 highly unusual, ≤−2 unusually low; at least 5 cell-days needed to flag). **Critical windows**: weeks above the area's 75th-percentile week in ≥50% of complete years. *Why robust statistics:* fire data are heavy-tailed, so median/MAD resist being skewed by extreme years.
7. **Persistent sources** (gas flares, kilns, industry): cells classified known-static (FIRMS type 1–3), suspected persistent (active ≥8 years and ≥10 months, no seasonal peak) or normal. Nothing is deleted; they can be filtered. *Why:* the challenge is about burning activity, and industrial heat sources would otherwise inflate it.

## 7. Validation results (real outputs of `validation/run_validation.py`; do not change or round them differently)

| Link | Total bias before | Total bias after | Spearman | 80% interval coverage |
|---|---|---|---|---|
| MODIS → S-NPP | −73.9% | +1.0% | 0.907 | 77.2% |
| NOAA-20 → S-NPP | +5.3% | −1.3% | 0.975 | 84.5% |
| NOAA-21 → S-NPP | +2.6% | −1.2% | 0.979 | 82.9% |
| Terra → S-NPP | −89.3% | −17.3% | 0.831 | 72.4% |

Artificial jump at each platform transition, measured against a control satellite present on both sides:

| Platform added | Naive merge | Harmonized |
|---|---|---|
| Aqua (2002) | +100% | −14% |
| S-NPP (2012) | +385% | +6% |
| NOAA-20 (2018) | +79% | +3% |
| NOAA-21 (2023) | +31% | −2% |

Agreement by scale (8-day Spearman): country 0.919, province 0.923, district 0.533.

## 8. Limitations: always state these honestly (judges reward this under Validity)

- S-NPP is a **reference scale, not ground truth**. Validation measures agreement between sensors, **not wildfire-detection accuracy**. Never claim "X% accurate fire detection".
- The model-selection rule (≤5% cross-validated bias) was added after the held-out results had been seen, so the test is not fully independent of that choice; all candidate models are reported.
- District estimates are much less reliable than province/country (0.53 vs 0.92); each area shows a reliability rating.
- The Terra-only years (2000–2002) have the weakest support; Terra's orbit has drifted (overpass ~10:50 → ~09:20 local time).
- The calibration is fitted for Pakistan only. With Punjab held out of the fit, Punjab is overestimated by 52%. It is never applied outside Pakistan.
- Near-real-time data after the last standard-quality date are provisional.
- No detection does not mean no fire (clouds, timing, detection limits). A hotspot is a thermal anomaly, not a confirmed wildfire; agricultural burning is included.
- The 2019 geoBoundaries layer does not separate Sherani from Zhob district, so the Sherani story uses an event box around the detections. **The press-report context in the Sherani story has not been verified yet: check it against a cited source before presenting it.**

## 9. Tech stack and project structure

- Backend: Python 3.13, FastAPI + DuckDB queries over Parquet files; pandas, numpy, pyarrow, pyproj, shapely, scipy, scikit-learn.
- Frontend: React 18, Vite 5, TypeScript, MapLibre GL 4, Apache ECharts 5. Basemap Esri World Dark Gray; optional NASA GIBS layer.

```
backend/ingestion/      downloader (resume, retries, checksums, manifest) and inventory
backend/processing/     normalizer (all FIRMS layouts), 1 km grid aggregation, persistent sources
backend/harmonization/  calibration.py (models, CV, intervals), harmonize.py (carrier plan, record)
backend/analytics/      anomaly.py, critical_windows.py
backend/services/       precompute.py (web files), custom_aoi.py, stories.py
backend/api/            main.py (all /api endpoints), data.py
frontend/src/           App.tsx, components/ (Calendar, FireMap, DayPanel, Kpis, Charts, Intel, Stories, Method)
validation/             run_validation.py -> results.json
scripts/                download_data.py, run_pipeline.py, run_eda.py, test_api_routes.py
docs/                   PROJECT_PLAN, PLAN_AMENDMENT_2, EDA_REPORT, VALIDATION_REPORT, DEMO_SCRIPT, screenshots/
tests/                  pytest suites (35 tests)
```

Ready-made screenshots for slides are in `docs/screenshots/` (dashboard, Sherani story, Punjab, method page, stories, mobile).

## 10. Running it on my laptop (Python 3.13)

**The NASA data is not in GitHub** (on purpose, it's ~400 MB and `.gitignore` excludes `data/`). Either the teammate who has it shares the `data/` folder privately (fastest), or I download and rebuild it myself.

Windows commands (on macOS/Linux use `.venv/bin/python` and `python3.13`):

```bash
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.lock.txt
```

`requirements.lock.txt` pins the exact tested versions (all have Python 3.13 wheels); prefer it over `requirements.txt`, which installs the newest versions.

If I don't have the `data/` folder:

1. Get my own free FIRMS MAP_KEY, copy `.env.example` to `.env`, set `FIRMS_MAP_KEY=` in it. **Never commit `.env`, never paste the key in a chat, a slide or a screenshot.**
2. `.venv/Scripts/python scripts/download_data.py --archive --boundaries` (no key needed)
3. `.venv/Scripts/python scripts/download_data.py --api-full` (needs the key)
4. `.venv/Scripts/python scripts/run_pipeline.py all`
5. `.venv/Scripts/python validation/run_validation.py`
6. `.venv/Scripts/python -c "from backend.services import precompute; precompute.build()"`

Then:

```bash
cd frontend && npm install && npm run build && cd ..
.venv/Scripts/python -m uvicorn backend.api.main:app --port 8000
```

Open http://localhost:8000. For frontend development, run `npm run dev` in `frontend/` (http://localhost:5173, proxies `/api` to port 8000, so **the backend must also be running**, otherwise every panel shows "500"). Tests: `.venv/Scripts/python -m pytest tests -q` (35 tests; the API tests need the processed data).

## 11. Rules for any changes you make

- Never invent data, row counts, accuracy numbers, or API responses; every number must come from the data or `validation/results.json`. Never replace real NASA data with synthetic data.
- Never expose the FIRMS key (frontend code, Git, logs, slides, chat).
- Never commit `data/`, `.env`, `.venv/` or logs.
- Do not claim a feature works without running it; run the tests after any backend change and check the app in a browser after frontend changes.
- Keep the limitations wording honest (section 8).
- Work on a branch and open a pull request instead of pushing straight to `main`, so the team can review.
- If you change the harmonization, rerun the pipeline, validation and precompute, and update README/VALIDATION_REPORT with the new real numbers.

## 12. Presentation: what I need from you

Build a **7-slide deck (hard limit, including title and intro slides)** and a **spoken script** for it, aimed at the five judging criteria. Suggested structure:

1. **Title**: FireSight, team name, challenge name, a hero screenshot of the calendar.
2. **The problem**: five satellites, records that don't agree; the 5.5× artificial jump in 2012 (naive) vs 1.13× (MODIS alone). Who needs this: emergency managers, land managers, scientists in Pakistan (seasonal agricultural burning, forest fires such as Sherani 2022). → Impact, Relevance.
3. **Our approach**: raw NASA FIRMS data → 1 km equal-area grid → 8-day calibration onto the S-NPP scale → one carrier sensor at a time → calendar, anomalies, windows. A simple pipeline diagram. → Creativity, Validity.
4. **Proof it works**: the before/after chart and the validation tables (bias −73.9% → +1.0%, transition jump +385% → +6%), held-out years. → Validity, Best Use of Science.
5. **The app**: calendar + map + now-vs-median + critical windows + CSV export + accessible palettes; screenshots. → Relevance, Presentation.
6. **Stories / real use**: Sherani pine forest fire area, 11–28 May 2022 flagged "highly unusual" (peak robust z ≈ 26 vs other years); Punjab's two burning seasons as recurring critical windows. Works anywhere FIRMS data exists (on-demand fetch). → Impact, Storytelling.
7. **Honesty and next steps**: limitations (reference scale not ground truth, district reliability, Pakistan-only calibration), and next steps (more countries, ground-truth burned-area comparison, alerts). Links: GitHub repo and NASA data credit.

Every slide should credit NASA FIRMS. The References field must list: NASA FIRMS (MODIS C6.1, VIIRS 375 m S-NPP/NOAA-20/NOAA-21), FIRMS missing-data table, geoBoundaries gbOpen, NASA GIBS, the Esri basemap, and the open-source libraries (FastAPI, DuckDB, pandas, numpy, pyarrow, pyproj, shapely, scipy, scikit-learn, React, Vite, TypeScript, MapLibre GL, Apache ECharts). Also see `docs/DEMO_SCRIPT.md` (a 3-minute live-demo script, useful for local judging but **too long for the 30-second video option**; if we choose a video, it needs a new 30-second script).
