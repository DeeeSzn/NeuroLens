"""A/B comparison service — compares two analysis results."""

from __future__ import annotations

import numpy as np

from app.services.brain_regions import REGION_ORDER
from app.services.tribe_wrapper import load_result


def compare_analyses(result_a: dict, result_b: dict) -> dict:
    """Compare two analysis results and return deltas + summary insights.

    Parameters
    ----------
    result_a, result_b : dict
        Full analysis result dicts (as returned by ``run_inference``).

    Returns
    -------
    dict
        ComparisonResult-compatible dict.
    """
    ts_a = result_a["timesteps"]
    ts_b = result_b["timesteps"]

    # Align to shorter length
    n = min(len(ts_a), len(ts_b))
    regions = REGION_ORDER
    tr = result_a.get("tr_seconds", 1.5)

    deltas: list[dict] = []
    cumulative = {r: 0.0 for r in regions}

    for i in range(n):
        delta = {"time_sec": round(i * tr, 2)}
        for r in regions:
            # .get guards legacy results saved before the named regions existed
            d = ts_b[i]["regions"].get(r, 0.0) - ts_a[i]["regions"].get(r, 0.0)
            delta[f"{r}_delta"] = round(d, 4)
            cumulative[r] += d
        deltas.append(delta)

    # Generate summary insights
    summary_parts: list[str] = []
    for r in regions:
        avg_delta = cumulative[r] / n if n > 0 else 0
        pct = avg_delta * 100
        direction = "higher" if pct > 0 else "lower"
        if abs(pct) > 1:
            summary_parts.append(
                f"Version B has {abs(pct):.1f}% {direction} {r} engagement overall."
            )

    # Find biggest time-range differences  
    detail_insights: list[str] = []
    for r in regions:
        arr_a = np.array([ts_a[i]["regions"].get(r, 0.0) for i in range(n)])
        arr_b = np.array([ts_b[i]["regions"].get(r, 0.0) for i in range(n)])
        diff = arr_b - arr_a
        if len(diff) == 0:
            continue
        max_idx = int(np.argmax(np.abs(diff)))
        if abs(diff[max_idx]) > 0.05:
            t = round(max_idx * tr, 2)
            direction = "higher" if diff[max_idx] > 0 else "lower"
            detail_insights.append(
                f"Largest {r} difference at {t}s: Version B is {abs(diff[max_idx]):.2f} "
                f"{direction}."
            )

    return {
        "summary": " ".join(summary_parts) if summary_parts else "Both versions show similar brain activation patterns.",
        "deltas": deltas,
        "insights": detail_insights,
    }
