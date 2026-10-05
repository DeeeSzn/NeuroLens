#!/usr/bin/env python
"""Run ONE inference locally (no Redis/Celery) with the in-process memory guard.

Usage (from backend/):
    ./venv/bin/python scripts/run_inference_local.py <file> <video|audio>

This is the same code path the Celery worker uses (app.services.tribe_wrapper.run_inference),
so it exercises the fp16 extractors + video batch size + memory guard exactly as a job would.
"""

import json
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S"
)

# Make `app` importable when run as `scripts/run_inference_local.py` from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import tribe_wrapper as tw  # noqa: E402


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: run_inference_local.py <file> <video|audio>")
        raise SystemExit(2)
    path, media_type = sys.argv[1], sys.argv[2]
    result = tw.run_inference(
        path, media_type, on_progress=lambda p: print(f"progress {p}", flush=True)
    )
    print(
        "DONE "
        + json.dumps(
            {k: result[k] for k in ("n_timesteps", "tr_seconds", "duration_sec")}
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
