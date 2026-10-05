"""Tests for the A/B comparison service."""

from app.services.comparison import compare_analyses


def _make_result(activations: list[dict[str, float]], tr: float = 1.5) -> dict:
    """Build a minimal analysis result dict."""
    timesteps = []
    for i, regions in enumerate(activations):
        timesteps.append({
            "time_sec": round(i * tr, 2),
            "regions": regions,
            "top_rois": [],
            "words": [],
        })
    return {
        "duration_sec": len(activations) * tr,
        "n_timesteps": len(activations),
        "tr_seconds": tr,
        "timesteps": timesteps,
    }


def test_identical_results():
    """Comparing identical results should show no significant differences."""
    regions = {"visual": 0.5, "auditory": 0.5, "language": 0.5, "prefrontal": 0.5, "multisensory": 0.5}
    result = _make_result([regions] * 5)
    comp = compare_analyses(result, result)

    assert "similar" in comp["summary"].lower() or all(
        abs(d["visual_delta"]) < 0.01 for d in comp["deltas"]
    )


def test_different_results():
    """Comparing different results should produce meaningful summary."""
    base = {"visual": 0.3, "auditory": 0.3, "language": 0.3, "prefrontal": 0.3, "multisensory": 0.3}
    enhanced = {"visual": 0.8, "auditory": 0.8, "language": 0.8, "prefrontal": 0.8, "multisensory": 0.8}

    result_a = _make_result([base] * 5)
    result_b = _make_result([enhanced] * 5)
    comp = compare_analyses(result_a, result_b)

    # Should indicate B is higher
    assert "higher" in comp["summary"].lower()
    assert len(comp["deltas"]) == 5
    assert comp["deltas"][0]["visual_delta"] > 0


def test_different_lengths():
    """Comparison should work with different length results (align to shorter)."""
    base = {"visual": 0.3, "auditory": 0.3, "language": 0.3, "prefrontal": 0.3, "multisensory": 0.3}
    result_a = _make_result([base] * 3)
    result_b = _make_result([base] * 7)
    comp = compare_analyses(result_a, result_b)
    assert len(comp["deltas"]) == 3


def test_legacy_results_missing_named_regions():
    """Pre-named-region (5-key) results must compare without raising."""
    legacy = {"visual": 0.3, "auditory": 0.3, "language": 0.3, "prefrontal": 0.3, "multisensory": 0.3}
    comp = compare_analyses(_make_result([legacy] * 4), _make_result([legacy] * 4))
    assert len(comp["deltas"]) == 4
    assert comp["deltas"][0]["tpoj_delta"] == 0.0
    assert comp["deltas"][0]["memory_delta"] == 0.0
    assert comp["deltas"][0]["face_body_delta"] == 0.0


def test_mixed_legacy_and_new_results():
    """Comparing a legacy result against an 8-key result must not raise."""
    legacy = {"visual": 0.3, "auditory": 0.3, "language": 0.3, "prefrontal": 0.3, "multisensory": 0.3}
    new = dict(legacy, tpoj=0.9, memory=0.9, face_body=0.9)
    comp = compare_analyses(_make_result([legacy] * 3), _make_result([new] * 3))
    assert comp["deltas"][0]["tpoj_delta"] == 0.9
    assert comp["deltas"][0]["visual_delta"] == 0.0
