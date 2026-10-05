"""Tests for the Markdown report export."""

from app.services.brain_regions import REGION_ORDER
from app.services.export import generate_text_report

LEGACY_REGIONS = ["visual", "auditory", "language", "prefrontal", "multisensory"]


def _result(regions):
    return {
        "duration_sec": 3.0,
        "n_timesteps": 2,
        "tr_seconds": 1.0,
        "timesteps": [
            {"time_sec": 0.0, "regions": regions, "top_rois": [], "words": []},
            {"time_sec": 1.0, "regions": regions, "top_rois": [], "words": []},
        ],
        "insights": [],
    }


def test_report_includes_all_regions():
    report = generate_text_report(
        _result({r: 0.4 for r in REGION_ORDER}), "job1", "clip.mp3"
    )
    for region in REGION_ORDER:
        label = "Prefrontal areas" if region == "mpfc_valuation" else region.replace("_", " ").capitalize()
        assert f"**{label}**" in report


def test_report_handles_legacy_five_key_result():
    legacy = {r: 0.4 for r in LEGACY_REGIONS}
    report = generate_text_report(_result(legacy), "job1", "clip.mp3")
    assert "**Visual**" in report
    assert "**Tpoj**" in report  # present but zero, must not raise


def test_audio_report_is_descriptive_and_uses_real_timestamps():
    result = _result({r: 0.4 for r in REGION_ORDER})
    result["insight_reference_version"] = "audio-pilot-v1"
    result["timesteps"][1]["time_sec"] = 5.0
    result["timesteps"][1]["regions"] = {**result["timesteps"][1]["regions"], "auditory": 0.9}
    report = generate_text_report(result, "job1", "clip.mp3", "audio")
    assert "**Reference:** audio-pilot-v1" in report
    assert "**Auditory**: avg 0.650, peak 0.900 at 5.0s" in report
    assert "**Visual**" not in report
    assert "**Face body**" not in report
    assert "## Predicted Response Findings" in report
