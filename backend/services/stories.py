"""Story Mode case studies.

Narrative context is limited to widely reported facts and is labelled as press-reported context.
Every number shown in a story is computed live from the FIRMS observations by the API.
"""

# Event box drawn around the May 2022 FIRMS detections on the Koh-e-Sulaiman / Shinghar ridge.
# geoBoundaries PAK ADM2 (2019 edition) does not separate Sherani district from Zhob, so the
# story uses its own event area instead of a district polygon.
SHERANI_BOX = [69.80, 31.25, 70.15, 31.62]

STORIES = [
    {
        "id": "sherani-2022",
        "title": "Sherani chilgoza pine forest fire",
        "subtitle": "Koh-e-Sulaiman range, Balochistan · May 2022",
        "aoi_id": "STORY-SHERANI",
        "aoi_name": "Sherani fire event area (story box)",
        "custom_polygon": {"type": "bbox", "bbox": SHERANI_BOX},
        "parent_aoi": "PAK-ADM2-19",
        "start": "2022-05-01", "end": "2022-06-10", "focus": "2022-05-20",
        "bounds": [69.6, 31.1, 70.35, 31.8],
        "context": [
            "In May 2022 a large fire burned the chilgoza (pine-nut) forest of Sherani district, in the "
            "Koh-e-Sulaiman range of north-eastern Balochistan, a range described as home to the world's largest "
            "pine-nut forest.",
            "The forests matter to local livelihoods: about half of the local population is reported to depend on "
            "income from chilgoza forests.",
            "An Iranian Il-76 air tanker joined the firefighting effort after the fire had burned for about two weeks.",
        ],
        "context_note": "Background from the press reports cited below. All figures in this story are computed "
                        "from NASA FIRMS data.",
        "sources": [
            {"label": "Arab News, 24 May 2022: “After two weeks raging, Iranian air tanker puts out forest "
                      "fire in southwest Pakistan”",
             "url": "https://arabnews.pk/node/2088541"},
            {"label": "The Friday Times, 20 Sep 2022: “Long-term impacts of ‘terrible’ fire season in "
                      "Pakistan’s mountains”",
             "url": "https://www.thefridaytimes.com/20-Sep-2022/long-term-impacts-of-terrible-fire-season-in-pakistan-s-mountains"},
        ],
        "boundary_note": "The geoBoundaries 2019 district layer used by FireSight does not separate Sherani "
                         "district; these detections fall inside the polygon labelled Zhob. The story therefore "
                         "uses an event box drawn around the detections.",
        "steps": [
            {"title": "Where the satellites saw it",
             "text": "Detections from MODIS (Terra, Aqua) and VIIRS (S-NPP, NOAA-20) cluster on the forested ridge.",
             "date": "2022-05-20", "range": ["2022-05-10", "2022-05-31"]},
            {"title": "How unusual it was",
             "text": "Compare the event area's May 2022 activity with the same weeks in other years on the calendar.",
             "date": "2022-05-20", "range": ["2022-05-10", "2022-05-31"]},
            {"title": "Which sensors contributed",
             "text": "VIIRS resolves many more 375 m pixels than MODIS at 1 km; the harmonized score puts both on one scale.",
             "date": "2022-05-20", "range": ["2022-05-01", "2022-06-10"]},
        ],
    },
    {
        "id": "punjab-seasons",
        "title": "Punjab's two burning seasons",
        "subtitle": "Seasonal vegetation-burning activity · 2000–2026",
        "aoi_id": "PAK-ADM1-5",
        "start": "2025-10-01", "end": "2025-11-30", "focus": "2025-11-05",
        "bounds": [69.2, 27.6, 75.4, 34.1],
        "context": [
            "Punjab is Pakistan's main agricultural province. Its FIRMS detections are dominated by two recurring "
            "seasons each year, visible as bands on the burning calendar.",
            "The timing of these bands coincides with the wheat (April–May) and rice (October–November) harvest "
            "periods. FIRMS cannot tell what was burned; FireSight describes this as vegetation-burning activity.",
        ],
        "context_note": "The link to crop-residue burning is an interpretation of the timing, not something the "
                        "satellite record establishes on its own.",
        "steps": [
            {"title": "The autumn season",
             "text": "October–November detections across the irrigated plains.",
             "date": "2025-11-05", "range": ["2025-10-25", "2025-11-15"]},
            {"title": "The spring season",
             "text": "A second band in late April and May.",
             "date": "2025-05-05", "range": ["2025-04-25", "2025-05-15"]},
            {"title": "Recurring windows",
             "text": "The critical-windows panel shows how many years each week was elevated.",
             "date": "2025-11-05", "range": ["2025-10-25", "2025-11-15"]},
        ],
    },
]
