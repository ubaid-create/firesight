# FireSight — Demo Script (about 3 minutes)

Start the app first and open http://localhost:8000.

```bash
.venv/Scripts/python -m uvicorn backend.api.main:app --port 8000
```

| Time | Screen | What to say |
|---|---|---|
| 0:00 | Dashboard, Pakistan | "Five satellites have watched Pakistan burn since 2000, but their records don't agree. FireSight turns them into one consistent fire history." |
| 0:15 | Scroll to *Before and after harmonization* (year view) | "The red dashed line is what you get by merging the raw detections. It jumps 5.5× in 2012 when VIIRS arrives, while MODIS alone barely changes. The white line is FireSight's harmonized record on one scale." |
| 0:40 | *Burning activity calendar* | "This is the burning calendar, every day since 2000. You can see the spring band in May and the autumn band from October to November, recurring every year. Before 2012 the values are reconstructed from MODIS; the tooltip says so, with an uncertainty interval." |
| 1:00 | Click a day in early May; the map and day panel update | "Click any day: the map shows each satellite's detections, and the panel shows what each platform saw. Raw counts differ by sensor; the harmonized index doesn't." |
| 1:20 | *Fire stories* → Sherani | "In May 2022 the chilgoza pine forests of Sherani burned. FireSight puts the event area on the map, shows MODIS and VIIRS detections, and flags the period as highly unusual against 25 other years." |
| 1:50 | Top cards: *Now vs historical median* | "The same dates in every year, compared like for like. The latest weeks are flagged provisional because they rely on near-real-time data. After S-NPP stopped on 2 November 2026, NOAA-21 carries the record, calibrated to within about 1% on held-out data." |
| 2:15 | *Method & validation* page | "Every number here is computed and tested on held-out years. We also show the limits: district estimates are less reliable, the earliest Terra years have the weakest support, and our calibration is never applied outside Pakistan." |
| 2:40 | Back to the map: *Draw area* or a coordinate box outside Pakistan → *Fetch last 5 days* | "The app works anywhere FIRMS data can be fetched. Outside our processed region it shows raw recent detections and says clearly that no harmonized history exists there." |
| 2:55 | — | "FireSight: one Earth, multiple satellites, one harmonized fire history." |

## Before recording

- Check that the API is running and the dashboard shows the latest date.
- Pre-open `/?story=sherani-2022` in a second tab as a backup.
- The on-demand fetch needs internet access and the FIRMS key in `.env`.
- Check the Sherani press-report context against your own cited sources before presenting it.
