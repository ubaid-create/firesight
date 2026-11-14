"""Run FireSight processing stages. Each stage is safe to rerun.

  python scripts/run_pipeline.py normalize
  python scripts/run_pipeline.py aggregate
  python scripts/run_pipeline.py calibrate
  python scripts/run_pipeline.py harmonize
  python scripts/run_pipeline.py all
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

STAGES = ["normalize", "aggregate", "calibrate", "harmonize"]


def run(stage: str):
    t = time.time()
    if stage == "normalize":
        from backend.processing import normalizer
        rep = normalizer.build()
    elif stage == "aggregate":
        from backend.processing import aggregate
        rep = aggregate.build()
    elif stage == "calibrate":
        from backend.harmonization import calibration
        rep = calibration.build()
    elif stage == "harmonize":
        from backend.harmonization import harmonize
        rep = harmonize.build()
    else:
        raise SystemExit(f"unknown stage {stage}")
    print(f"== {stage} done in {time.time() - t:.1f}s")
    print(json.dumps(rep, indent=1, default=str)[:6000])


if __name__ == "__main__":
    want = sys.argv[1:] or ["all"]
    for s in (STAGES if want == ["all"] else want):
        run(s)
