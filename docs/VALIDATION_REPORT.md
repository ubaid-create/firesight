# FireSight — Validation Report

Generated from the processed data on 2026-11-14 14:23. Every figure below is computed by `validation/run_validation.py`.

VIIRS S-NPP is the chosen reference scale, not ground truth. The figures describe agreement between sensors, not fire-detection accuracy.
Unit: *cell-days* = sum over days of unique active 1 km cells (default filter: vegetation-fire type or untyped, nominal or high confidence).

## 1. Calibration links: held-out results

Units are 8-day windows per province (ADM1). The model for each link was chosen by blocked cross-validation inside the training years only; the test years were scored once.

| Link | Train | Test | Windows (train / test) | Chosen model | Uncalibrated total bias | Calibrated total bias | MAE | Mean reference | Spearman | 80% interval coverage |
|---|---|---|---|---|---|---|---|---|---|---|
| MODIS_to_SNPP | 2012-02-01 – 2021-12-31 | 2022-01-01 – 2025-12-31 | 3,192 / 1,288 | loglinear_month_scaled | -73.9% | 1.0% | 48.6 | 129.6 | 0.907 | 77.2% |
| Terra_to_SNPP | 2012-02-01 – 2021-12-31 | 2022-01-01 – 2025-12-31 | 3,192 / 1,288 | loglinear_month_scaled | -89.3% | -17.3% | 90.4 | 129.6 | 0.831 | 72.4% |
| Terra_to_MODIS | 2003-01-01 – 2014-12-31 | 2015-01-01 – 2025-12-31 | 3,864 / 3,542 | loglinear_month_scaled | -56.6% | -12.2% | 13.8 | 32.5 | 0.899 | 80.8% |
| NOAA20_to_SNPP | 2018-04-01 – 2022-12-31 | 2023-01-01 – 2025-12-31 | 1,526 / 966 | loglinear_month | 5.3% | -1.3% | 18.6 | 131.8 | 0.975 | 84.5% |
| NOAA21_to_SNPP | 2023-03-01 – 2024-12-31 | 2025-01-01 – 2026-07-31 | 588 / 504 | loglinear_month_scaled | 2.6% | -1.2% | 16.3 | 135.9 | 0.979 | 82.9% |

### Held-out total bias by year (chosen model)

| Link | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MODIS_to_SNPP |  |  |  |  |  |  |  | 5.8% | -1.2% | 1.1% | -1.5% |  |
| Terra_to_SNPP |  |  |  |  |  |  |  | -8.7% | -23.3% | -18.0% | -19.1% |  |
| Terra_to_MODIS | 1.4% | -10.9% | 3.7% | 2.0% | -14.6% | -19.5% | -25.3% | -13.8% | -20.5% | -20.2% | -16.3% |  |
| NOAA20_to_SNPP |  |  |  |  |  |  |  |  | -3.4% | 1.9% | -2.6% |  |
| NOAA21_to_SNPP |  |  |  |  |  |  |  |  |  |  | -3.7% | 4.1% |

### All candidate models (cross-validation in training years, then test)

**MODIS_to_SNPP**

| Model | CV log-MAE | CV total bias | Test log-MAE | Test MAE | Test total bias | Test Spearman |
|---|---|---|---|---|---|---|
| ratio | 0.697 | -0.0% | 0.700 | 50.6 | 0.5% | 0.904 |
| month_ratio | 0.652 | 1.0% | 0.681 | 42.7 | 3.0% | 0.898 |
| region_ratio | 0.698 | -0.0% | 0.709 | 51.7 | 1.7% | 0.901 |
| region_season_ratio | 0.660 | 0.8% | 0.680 | 46.1 | 3.3% | 0.902 |
| loglinear_month | 0.625 | 24.9% | 0.656 | 63.2 | 25.7% | 0.907 |
| loglinear_month_scaled (chosen) | 0.647 | 0.4% | 0.676 | 48.6 | 1.0% | 0.907 |

**Terra_to_SNPP**

| Model | CV log-MAE | CV total bias | Test log-MAE | Test MAE | Test total bias | Test Spearman |
|---|---|---|---|---|---|---|
| ratio | 0.905 | 0.2% | 1.012 | 94.2 | -10.3% | 0.822 |
| month_ratio | 0.869 | 0.7% | 0.976 | 79.3 | -20.6% | 0.824 |
| region_ratio | 0.913 | 0.3% | 1.006 | 87.4 | -13.2% | 0.824 |
| region_season_ratio | 0.857 | 0.0% | 0.947 | 73.2 | -23.3% | 0.836 |
| loglinear_month | 0.809 | 17.6% | 0.957 | 99.9 | -3.5% | 0.831 |
| loglinear_month_scaled (chosen) | 0.820 | 0.9% | 0.968 | 90.4 | -17.3% | 0.831 |

**Terra_to_MODIS**

| Model | CV log-MAE | CV total bias | Test log-MAE | Test MAE | Test total bias | Test Spearman |
|---|---|---|---|---|---|---|
| ratio | 0.361 | 0.1% | 0.398 | 12.7 | -12.0% | 0.895 |
| month_ratio | 0.368 | 0.4% | 0.398 | 11.6 | -9.7% | 0.895 |
| region_ratio | 0.353 | 0.2% | 0.388 | 12.0 | -12.4% | 0.896 |
| region_season_ratio | 0.336 | -0.0% | 0.360 | 9.9 | -8.8% | 0.900 |
| loglinear_month | 0.295 | 7.2% | 0.348 | 14.8 | -6.0% | 0.899 |
| loglinear_month_scaled (chosen) | 0.299 | 0.2% | 0.352 | 13.8 | -12.2% | 0.899 |

**NOAA20_to_SNPP**

| Model | CV log-MAE | CV total bias | Test log-MAE | Test MAE | Test total bias | Test Spearman |
|---|---|---|---|---|---|---|
| ratio | 0.300 | 0.0% | 0.280 | 18.3 | 1.5% | 0.976 |
| month_ratio | 0.300 | 0.1% | 0.281 | 18.5 | 1.5% | 0.976 |
| region_ratio | 0.298 | 0.0% | 0.278 | 18.3 | 1.7% | 0.976 |
| region_season_ratio | 0.298 | 0.0% | 0.279 | 18.7 | 1.7% | 0.976 |
| loglinear_month (chosen) | 0.274 | -3.0% | 0.253 | 18.6 | -1.3% | 0.975 |
| loglinear_month_scaled | 0.275 | 0.0% | 0.256 | 18.4 | 1.7% | 0.975 |

**NOAA21_to_SNPP**

| Model | CV log-MAE | CV total bias | Test log-MAE | Test MAE | Test total bias | Test Spearman |
|---|---|---|---|---|---|---|
| ratio | 0.277 | -0.2% | 0.255 | 15.3 | -1.4% | 0.978 |
| month_ratio | 0.281 | -0.9% | 0.254 | 16.8 | -0.6% | 0.979 |
| region_ratio | 0.280 | 0.4% | 0.261 | 15.3 | -1.1% | 0.978 |
| region_season_ratio | 0.286 | -0.3% | 0.262 | 15.5 | -0.1% | 0.978 |
| loglinear_month | 0.261 | -0.1% | 0.234 | 16.3 | -1.0% | 0.979 |
| loglinear_month_scaled (chosen) | 0.261 | -0.4% | 0.234 | 16.3 | -1.2% | 0.979 |

## 2. Raw MODIS versus raw S-NPP (Pakistan)

| Year | MODIS cell-days | S-NPP cell-days | Ratio | MODIS detections | S-NPP detections | Ratio |
|---|---|---|---|---|---|---|
| 2013 | 8,479 | 32,283 | 3.81 | 8,615 | 37,750 | 4.38 |
| 2014 | 9,617 | 38,754 | 4.03 | 9,806 | 45,596 | 4.65 |
| 2015 | 8,116 | 32,458 | 4.0 | 8,238 | 37,923 | 4.6 |
| 2016 | 10,071 | 41,457 | 4.12 | 10,264 | 50,405 | 4.91 |
| 2017 | 11,446 | 42,084 | 3.68 | 11,665 | 50,099 | 4.29 |
| 2018 | 11,971 | 42,636 | 3.56 | 12,184 | 50,702 | 4.16 |
| 2019 | 8,793 | 35,169 | 4.0 | 8,928 | 41,294 | 4.63 |
| 2020 | 9,057 | 36,283 | 4.01 | 9,204 | 42,723 | 4.64 |
| 2021 | 11,940 | 48,800 | 4.09 | 12,169 | 57,909 | 4.76 |
| 2022 | 10,583 | 39,601 | 3.74 | 10,830 | 48,093 | 4.44 |
| 2023 | 9,698 | 37,185 | 3.83 | 9,852 | 43,396 | 4.4 |
| 2024 | 11,475 | 43,439 | 3.79 | 11,708 | 53,084 | 4.53 |
| 2025 | 11,813 | 46,680 | 3.95 | 12,022 | 57,456 | 4.78 |

S-NPP / MODIS cell-day ratio by calendar month, 2013–2025: 1: 2.86, 2: 2.73, 3: 2.93, 4: 3.15, 5: 4.18, 6: 6.82, 7: 5.76, 8: 2.8, 9: 7.0, 10: 5.67, 11: 4.87, 12: 4.21

## 3. Platform transitions: naive merge versus harmonized record

Ratio of mean annual activity after a platform was added to mean annual activity before. The control series is a platform that existed on both sides, so its ratio reflects real change in fire activity. "Excess" is how far a series departs from the control.

| Transition | Years before → after | Control | Control ratio | Naive merge ratio | Naive excess | Harmonized ratio | Harmonized excess |
|---|---|---|---|---|---|---|---|
| Aqua added (2002) | 2001–2001 → 2003–2005 | terra_only | 1.23 | 2.47 | 100.4% | 1.06 | -13.7% |
| S-NPP added (2012) | 2009–2011 → 2013–2015 | modis_only | 1.13 | 5.47 | 384.5% | 1.20 | 6.2% |
| NOAA-20 added (2018) | 2015–2017 → 2019–2021 | modis_only | 1.01 | 1.80 | 79.1% | 1.04 | 3.1% |
| NOAA-21 added (2023) | 2020–2022 → 2024–2025 | modis_only | 1.11 | 1.45 | 31.1% | 1.08 | -2.0% |

The harmonized values before 2012 come from a calibration fitted on 2012–2021, so the 2012 row is not an independent test: no VIIRS data exist before 2012 to test against. The independent evidence is the held-out table in section 1.

## 4. Agreement by spatial scale (calibrated MODIS versus observed S-NPP, test years)

| Scale | AOIs | 8-day MAE | 8-day mean reference | 8-day total bias | 8-day Spearman | 8-day interval coverage | Daily MAE | Daily mean reference | Daily Spearman |
|---|---|---|---|---|---|---|---|---|---|
| ADM0 | 1 | 325.1 | 915.6 | -2.0% | 0.919 | 79.1% | 75.6 | 114.6 | 0.731 |
| ADM1 | 7 | 55.0 | 130.8 | -2.1% | 0.923 | 79.1% | 12.8 | 16.4 | 0.494 |
| ADM2 | 126 | 4.6 | 7.3 | -2.2% | 0.533 | 59.9% | 1.0 | 0.9 | 0.177 |

## 5. Sensitivity of the MODIS → S-NPP link

| Variant | S-NPP per MODIS (training) | Test MAE | Test mean reference | Test total bias | Test Spearman |
|---|---|---|---|---|---|
| 1 km grid (default) | 3.827 | 48.6 | 129.6 | 1.0% | 0.907 |
| 2 km grid | 3.87 | 44.3 | 119.0 | 1.3% | 0.906 |
| near-nadir pixels only | 4.269 | 47.3 | 117.8 | 1.2% | 0.894 |
| including low confidence | 4.249 | 56.6 | 149.9 | -1.1% | 0.906 |
| excluding suspected persistent sources | 3.765 | 47.5 | 126.9 | 1.2% | 0.906 |

## 6. Geographic holdout (MODIS → S-NPP)

Model fitted on the other provinces (training years), scored on the held-out province (test years).

| Held-out province | Windows | Windows with S-NPP activity | Mean reference | MAE | Total bias | Spearman |
|---|---|---|---|---|---|---|
| Balochistan | 184 | 179 | 45.0 | 21.2 | -26.3% | 0.891 |
| Sindh | 184 | 183 | 121.1 | 54.3 | 4.1% | 0.893 |
| Gilgit-Baltistan | 184 | 65 | 1.5 | 1.9 | 55.1% | 0.382 |
| Azad Kashmir | 184 | 135 | 15.7 | 12.3 | -2.5% | 0.607 |
| Khyber Pakhtunkhwa | 184 | 182 | 99.3 | 40.1 | -16.6% | 0.918 |
| Punjab | 184 | 183 | 623.7 | 406.6 | 51.6% | 0.940 |
| Islamabad Capital Territory | 184 | 77 | 1.2 | 2.2 | 146.8% | 0.277 |

## 7. Cross-sensor correspondence (Aqua versus S-NPP, daytime, same day)

| Period | Aqua cell-days | S-NPP cell-days | Aqua cells with S-NPP in same cell | Aqua cells with S-NPP within one cell | S-NPP cells with Aqua within one cell |
|---|---|---|---|---|---|
| 2012-2021 | 53,335 | 335,588 | 64.7% | 95.4% | 61.0% |
| 2022-2025 | 25,208 | 144,165 | 61.9% | 94.7% | 60.1% |

A same-day match within one cell is evidence of correspondence, not proof that both sensors saw the same fire.
