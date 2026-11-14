# FireSight — Exploratory Data Analysis and Quality Report

Generated 2026-11-14 13:32 by `scripts/run_eda.py` from `data/processed/normalized/detections.parquet`.

## 1. What was loaded

- Raw files read: 509 (2,374,206 rows).
- Rows outside Pakistan (API requests use a bounding box that covers neighbouring countries): 502,711, excluded from the Pakistan tables.
- Near-real-time rows superseded by standard data for the same platform and date: 0.
- Exact duplicates (same platform, time, position): 0.
- Detections kept: 1,871,495, from 2000-11-01 to 2026-11-13. Null timestamps: 0.
- Pakistan area used (sum of 7 ADM1 units): 876,059 km².

## 2. Detections by platform and processing level

| Platform | NRT | SP |
|---|---|---|
| Terra | 90 | 113,580 |
| Aqua | 2,349 | 125,861 |
| SNPP | 9,373 | 855,518 |
| NOAA20 | 14,070 | 522,640 |
| NOAA21 | 13,252 | 214,762 |

| Platform | First detection in Pakistan | Last detection |
|---|---|---|
| Terra | 2000-11-01 | 2026-11-10 |
| Aqua | 2002-07-06 | 2026-11-13 |
| SNPP | 2012-01-20 | 2026-11-02 |
| NOAA20 | 2018-04-01 | 2026-11-13 |
| NOAA21 | 2023-03-01 | 2026-11-13 |

## 3. Detections per year

| Year | Terra | Aqua | SNPP | NOAA20 | NOAA21 |
|---|---|---|---|---|---|
| 2000 | 419 | 0 | 0 | 0 | 0 |
| 2001 | 3,063 | 0 | 0 | 0 | 0 |
| 2002 | 3,260 | 1,122 | 0 | 0 | 0 |
| 2003 | 3,485 | 3,518 | 0 | 0 | 0 |
| 2004 | 4,178 | 3,954 | 0 | 0 | 0 |
| 2005 | 3,691 | 4,038 | 0 | 0 | 0 |
| 2006 | 2,928 | 2,825 | 0 | 0 | 0 |
| 2007 | 3,517 | 3,497 | 0 | 0 | 0 |
| 2008 | 4,889 | 5,468 | 0 | 0 | 0 |
| 2009 | 4,158 | 4,582 | 0 | 0 | 0 |
| 2010 | 3,681 | 4,232 | 0 | 0 | 0 |
| 2011 | 4,359 | 3,914 | 0 | 0 | 0 |
| 2012 | 6,203 | 5,852 | 55,484 | 0 | 0 |
| 2013 | 4,227 | 4,735 | 49,224 | 0 | 0 |
| 2014 | 4,816 | 5,353 | 56,750 | 0 | 0 |
| 2015 | 4,294 | 4,252 | 48,235 | 0 | 0 |
| 2016 | 4,753 | 5,970 | 62,111 | 0 | 0 |
| 2017 | 5,928 | 6,192 | 64,241 | 0 | 0 |
| 2018 | 6,318 | 6,518 | 63,657 | 46,098 | 0 |
| 2019 | 4,144 | 5,338 | 52,822 | 54,144 | 0 |
| 2020 | 4,052 | 5,734 | 52,347 | 54,180 | 0 |
| 2021 | 4,809 | 8,054 | 69,080 | 71,958 | 0 |
| 2022 | 4,939 | 6,490 | 60,493 | 61,891 | 0 |
| 2023 | 4,121 | 6,278 | 52,198 | 54,127 | 41,704 |
| 2024 | 4,964 | 7,350 | 66,073 | 71,325 | 68,082 |
| 2025 | 5,187 | 7,439 | 69,176 | 71,585 | 68,973 |
| 2026 | 3,287 | 5,505 | 43,000 | 51,402 | 49,255 |

## 4. Seasonal distribution (share of each platform's detections by month, %)

| Month | Terra | Aqua | SNPP | NOAA20 | NOAA21 |
|---|---|---|---|---|---|
| 1 | 12.00 | 11.40 | 7.80 | 7.30 | 7.10 |
| 2 | 22.20 | 16.60 | 12.70 | 11.60 | 10.60 |
| 3 | 12.40 | 7.10 | 6.80 | 5.30 | 6.20 |
| 4 | 8.70 | 4.50 | 6.40 | 7.20 | 7.10 |
| 5 | 23.20 | 13.50 | 21.70 | 20.40 | 20.10 |
| 6 | 4.10 | 3.10 | 7.50 | 8.50 | 9.80 |
| 7 | 1.50 | 1.40 | 2.10 | 2.70 | 2.90 |
| 8 | 1.40 | 1.50 | 1.00 | 1.20 | 1.10 |
| 9 | 1.00 | 1.40 | 2.20 | 2.20 | 2.40 |
| 10 | 2.20 | 9.30 | 10.20 | 12.20 | 12.70 |
| 11 | 3.70 | 20.50 | 13.60 | 14.30 | 13.20 |
| 12 | 7.60 | 9.80 | 7.80 | 7.10 | 6.80 |

## 5. Detection type (standard data only; near-real-time data carry no type)

0 = presumed vegetation fire, 1 = active volcano, 2 = other static land source, 3 = offshore.

| Type | Terra | Aqua | SNPP | NOAA20 | NOAA21 |
|---|---|---|---|---|---|
| untyped (NRT) | 90 | 2,349 | 9,373 | 14,070 | 13,252 |
| 0 | 112,479 | 124,694 | 797,655 | 491,564 | 202,629 |
| 2 | 968 | 1,098 | 57,568 | 30,898 | 12,049 |
| 3 | 133 | 69 | 295 | 178 | 84 |

## 6. Confidence (sensor-specific; the two scales are not equivalent)

MODIS: numeric 0–100, classed here as low < 30, nominal 30–79, high ≥ 80. VIIRS: delivered as low / nominal / high.

| Class (% of platform) | Terra | Aqua | SNPP | NOAA20 | NOAA21 |
|---|---|---|---|---|---|
| high | 11.60 | 9.70 | 2.60 | 2.50 | 3.10 |
| low | 3.90 | 3.60 | 13.20 | 13.70 | 14.20 |
| nominal | 84.50 | 86.70 | 84.20 | 83.80 | 82.70 |

MODIS raw confidence percentiles (5/25/50/75/95): 32, 51, 61, 71, 86

Default analysis filter (type 0 or untyped, nominal or high confidence) keeps 1,540,654 of 1,871,495 detections.

## 7. Product versions

| Version | Terra | Aqua | SNPP | NOAA20 | NOAA21 |
|---|---|---|---|---|---|
| 2 | 0 | 0 | 855,518 | 522,640 | 214,762 |
| 2.0NRT | 0 | 0 | 9,373 | 14,070 | 13,252 |
| 6.03 | 24,262 | 32,134 | 0 | 0 | 0 |
| 6.1NRT | 90 | 2,349 | 0 | 0 | 0 |
| 6.2 | 71,849 | 69,504 | 0 | 0 | 0 |
| 61.03 | 17,469 | 24,223 | 0 | 0 | 0 |

## 8. Overpass time: median local solar time of daytime detections

Local solar time = UTC + longitude / 15 hours. A change over the years indicates orbit drift, which changes what part of the daily fire cycle a satellite sees.

| Year | Terra | Aqua | SNPP | NOAA20 | NOAA21 |
|---|---|---|---|---|---|
| 2000 | 11.02 |  |  |  |  |
| 2001 | 10.96 |  |  |  |  |
| 2002 | 10.84 | 13.22 |  |  |  |
| 2003 | 10.83 | 13.19 |  |  |  |
| 2004 | 10.79 | 13.20 |  |  |  |
| 2005 | 10.81 | 13.19 |  |  |  |
| 2006 | 10.80 | 13.24 |  |  |  |
| 2007 | 10.82 | 13.26 |  |  |  |
| 2008 | 10.82 | 13.27 |  |  |  |
| 2009 | 10.83 | 13.31 |  |  |  |
| 2010 | 10.81 | 13.25 |  |  |  |
| 2011 | 10.81 | 13.25 |  |  |  |
| 2012 | 10.82 | 13.26 | 13.04 |  |  |
| 2013 | 10.82 | 13.25 | 13.07 |  |  |
| 2014 | 10.82 | 13.27 | 13.14 |  |  |
| 2015 | 10.82 | 13.26 | 13.13 |  |  |
| 2016 | 10.83 | 13.26 | 13.09 |  |  |
| 2017 | 10.82 | 13.25 | 13.07 |  |  |
| 2018 | 10.81 | 13.25 | 13.08 | 13.09 |  |
| 2019 | 10.83 | 13.24 | 13.09 | 13.11 |  |
| 2020 | 10.82 | 13.25 | 13.08 | 13.13 |  |
| 2021 | 10.80 | 13.26 | 13.07 | 13.12 |  |
| 2022 | 10.68 | 13.31 | 13.09 | 13.14 |  |
| 2023 | 10.45 | 13.52 | 13.13 | 13.10 | 13.10 |
| 2024 | 10.15 | 13.87 | 13.08 | 13.11 | 13.09 |
| 2025 | 9.81 | 14.39 | 13.13 | 13.09 | 13.09 |
| 2026 | 9.34 | 15.15 | 13.24 | 13.19 | 13.13 |

Night-time detections, median local solar time (hours):

| Platform | median | size |
|---|---|---|
| Terra | -1.96 | 9,343 |
| Aqua | 1.98 | 3,196 |
| SNPP | 1.78 | 155,154 |
| NOAA20 | 1.77 | 92,089 |
| NOAA21 | 1.77 | 41,185 |

## 9. Day / night split and pixel size

| Platform | D | N | night share % |
|---|---|---|---|
| Terra | 104,327 | 9,343 | 8.20 |
| Aqua | 125,014 | 3,196 | 2.50 |
| SNPP | 709,737 | 155,154 | 17.90 |
| NOAA20 | 444,621 | 92,089 | 17.20 |
| NOAA21 | 186,829 | 41,185 | 18.10 |

| Platform | scan median km | scan 90th pct km | scan 99th pct km |
|---|---|---|---|
| Terra | 1.10 | 1.90 | 3.70 |
| Aqua | 1.10 | 1.90 | 3.60 |
| SNPP | 0.43 | 0.56 | 0.73 |
| NOAA20 | 0.43 | 0.56 | 0.73 |
| NOAA21 | 0.43 | 0.56 | 0.73 |

## 10. Fire radiative power (MW per detection, default filter not applied)

| Platform | median | 90th pct | 99th pct |
|---|---|---|---|
| Terra | 11.80 | 31.60 | 81.60 |
| Aqua | 10.80 | 30.60 | 86.60 |
| SNPP | 3.60 | 9.70 | 26.80 |
| NOAA20 | 3.70 | 9.70 | 25.60 |
| NOAA21 | 4.40 | 11.80 | 30.20 |

FRP is not comparable across MODIS and VIIRS pixels and is never summed across sensors.

## 11. Overpasses with detections per day

Distinct acquisition times per platform-day (Pakistan). Hotspot files only list overpasses that produced detections, so this is a lower bound on observation opportunity.

| Platform | mean | max |
|---|---|---|
| Terra | 2.41 | 7.00 |
| Aqua | 2.04 | 7.00 |
| SNPP | 7.65 | 16.00 |
| NOAA20 | 7.55 | 17.00 |
| NOAA21 | 7.47 | 15.00 |

## 12. Regions

| Province / territory | area km² | Terra | Aqua | SNPP | NOAA20 | NOAA21 |
|---|---|---|---|---|---|---|
| Balochistan | 352,521 | 3,479 | 3,291 | 34,743 | 24,809 | 13,658 |
| Sindh | 137,721 | 30,194 | 16,495 | 140,297 | 74,103 | 30,513 |
| Gilgit-Baltistan | 69,077 | 249 | 163 | 1,552 | 1,053 | 326 |
| Azad Kashmir | 12,392 | 1,240 | 1,433 | 13,368 | 8,023 | 3,713 |
| Khyber Pakhtunkhwa | 101,530 | 10,529 | 11,924 | 86,661 | 54,184 | 25,206 |
| Punjab | 201,926 | 67,866 | 94,730 | 587,108 | 373,807 | 154,368 |
| Islamabad Capital Territory | 893 | 113 | 174 | 1,162 | 731 | 230 |

## 13. Persistent thermal sources (1 km cells)

- Cells with any detection: 218,507.
- Known static (FIRMS type 1, 2 or 3 in at least half of the typed detections): 511.
- Suspected persistent (active in ≥ 8 years and ≥ 10 calendar months, busiest month ≤ 25% of active days): 214.
- Normal / seasonal: 217,782.
- Untyped near-real-time rows: 39,134; of these 3,030 fall in known static cells and are left out of the default view (kept in the data).

Ten most active suspected persistent cells:

| # | active_days | years_active | months_active | max_month_share | lon | lat |
|---|---|---|---|---|---|---|
| 0 | 457.00 | 15.00 | 12.00 | 0.17 | 71.52 | 33.23 |
| 1 | 436.00 | 15.00 | 12.00 | 0.13 | 74.18 | 32.13 |
| 2 | 432.00 | 15.00 | 12.00 | 0.15 | 74.18 | 32.10 |
| 3 | 389.00 | 15.00 | 12.00 | 0.13 | 74.18 | 31.65 |
| 4 | 369.00 | 16.00 | 12.00 | 0.19 | 73.16 | 33.14 |
| 5 | 368.00 | 15.00 | 12.00 | 0.17 | 72.86 | 33.85 |
| 6 | 352.00 | 15.00 | 12.00 | 0.14 | 71.19 | 33.29 |
| 7 | 345.00 | 14.00 | 12.00 | 0.12 | 72.60 | 33.34 |
| 8 | 325.00 | 16.00 | 12.00 | 0.22 | 68.63 | 28.61 |
| 9 | 301.00 | 13.00 | 12.00 | 0.15 | 68.64 | 28.61 |
