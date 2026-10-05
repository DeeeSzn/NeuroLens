"""Tests for exploratory, reference-relative predicted response findings."""

from app.services.insights import generate_insights


def _make_timesteps(n: int, pattern: dict[str, list[float]]) -> list[dict]:
    """Build synthetic timestep data from region activation patterns."""
    timesteps = []
    for i in range(n):
        regions = {}
        for region, values in pattern.items():
            regions[region] = values[i % len(values)]
        timesteps.append({
            "time_sec": i * 1.5,
            "regions": regions,
            "top_rois": [],
            "words": [],
        })
    return timesteps


def _reference(media_type: str = "audio") -> dict:
    from app.services.brain_regions import REGION_GROUPS

    regions = {region: {"mean": 0.4, "variance": 0.01} for region in REGION_GROUPS}
    return {
        "version": "audio-pilot-v1", "media_type": media_type,
        "clips": {fingerprint: {"regions": regions} for fingerprint in ("source", "other-a", "other-b")},
    }


def test_detect_attention_peak():
    # 10 timesteps: low baseline with spike at steps 4-5
    da = [0.1, 0.1, 0.1, 0.1, 0.9, 0.9, 0.1, 0.1, 0.1, 0.1]
    pattern = {
        "visual": [0.3] * 10,
        "auditory": [0.3] * 10,
        "language": [0.3] * 10,
        "dorsal_attention": da,
        "multisensory": [0.3] * 10,
    }
    timesteps = _make_timesteps(10, pattern)
    insights = generate_insights(timesteps, tr_seconds=1.5, media_type="audio", reference=_reference(), source_fingerprint="source")

    peaks = [i for i in insights if i["type"] == "attention_response"]
    assert len(peaks) >= 1
    # The peak should cover the spike region (around 6.0s - 9.0s)
    peak = peaks[0]
    assert peak["time_start"] >= 4.5  # step 4 starts at 6.0s
    assert peak["z"] > 1.5
    assert peak["reference"]["n_clips"] == 2
    assert peak["confidence"] is None


def test_detect_attention_drop():
    da = [0.8, 0.8, 0.8, 0.05, 0.05, 0.05, 0.8, 0.8, 0.8, 0.8]
    pattern = {
        "visual": [0.5] * 10,
        "auditory": [0.5] * 10,
        "language": [0.5] * 10,
        "dorsal_attention": da,
        "multisensory": [0.5] * 10,
    }
    timesteps = _make_timesteps(10, pattern)
    insights = generate_insights(timesteps, tr_seconds=1.5, media_type="audio", reference=_reference())

    drops = [i for i in insights if i["type"] == "attention_response_low"]
    assert len(drops) >= 1


def test_detect_multisensory_integration():
    """Co-activation must not be labeled as integration or memorability."""
    n = 10
    pattern = {
        "visual": [0.1, 0.1, 0.1, 0.8, 0.8, 0.8, 0.1, 0.1, 0.1, 0.1],
        "auditory": [0.1, 0.1, 0.1, 0.7, 0.7, 0.7, 0.1, 0.1, 0.1, 0.1],
        "language": [0.1, 0.1, 0.1, 0.9, 0.9, 0.9, 0.1, 0.1, 0.1, 0.1],
        "dorsal_attention": [0.3] * 10,
        "multisensory": [0.3] * 10,
    }
    timesteps = _make_timesteps(n, pattern)
    insights = generate_insights(timesteps, tr_seconds=1.5, media_type="audio", reference=_reference())

    assert any(i["type"] == "auditory_response" for i in insights)
    assert all(i["claim_level"] == "descriptive" and "memorable" not in i["description"] for i in insights)


def test_detect_emotional_engagement():
    """A prefrontal rise is descriptive, not an emotion detector."""
    n = 10
    pattern = {
        "visual": [0.2] * 10,
        "auditory": [0.2] * 10,
        "language": [0.2] * 10,
        "dorsal_attention": [0.2] * 10,
        "mpfc_valuation": [0.1, 0.1, 0.1, 0.9, 0.9, 0.9, 0.1, 0.1, 0.1, 0.1],
        "multisensory": [0.1, 0.1, 0.1, 0.85, 0.85, 0.85, 0.1, 0.1, 0.1, 0.1],
    }
    timesteps = _make_timesteps(n, pattern)
    insights = generate_insights(timesteps, tr_seconds=1.5, media_type="audio", reference=_reference())

    assert any(i["type"] == "mpfc_response" for i in insights)
    assert all(i["type"] != "emotional" for i in insights)


def test_no_insights_for_flat_signal():
    """A flat signal at the benchmark mean should not trigger findings."""
    pattern = {
        "visual": [0.5] * 10,
        "auditory": [0.5] * 10,
        "language": [0.5] * 10,
        "dorsal_attention": [0.5] * 10,
        "mpfc_valuation": [0.5] * 10,
        "multisensory": [0.5] * 10,
    }
    timesteps = _make_timesteps(10, pattern)
    insights = generate_insights(timesteps, tr_seconds=1.5, media_type="audio", reference=_reference())
    assert insights == []


def test_empty_timesteps():
    """Empty input should return empty insights."""
    assert generate_insights([], 1.5) == []
    assert generate_insights([{"time_sec": 0, "regions": {"visual": 0.5, "auditory": 0.5, "language": 0.5, "dorsal_attention": 0.5, "multisensory": 0.5}, "top_rois": [], "words": []}], 1.5) == []


def test_no_reference_does_not_generate_benchmarked_findings():
    timesteps = _make_timesteps(10, {"auditory": [0.1] * 5 + [0.9] * 5})
    assert generate_insights(timesteps, 1.5, media_type="audio", reference=None) == []


def test_audio_cannot_report_visual_or_face_content():
    timesteps = _make_timesteps(6, {"visual": [0.9], "face_body": [0.9], "auditory": [0.4]})
    assert generate_insights(timesteps, 1.5, "audio", _reference()) == []
    video = generate_insights(timesteps, 1.5, "video", _reference("video"))
    assert {item["type"] for item in video} == {"visual_response", "face_area_response"}


def test_short_spike_and_discontinuous_windows_do_not_trigger():
    timesteps = _make_timesteps(5, {"auditory": [0.4, 0.9, 0.4, 0.4, 0.4]})
    assert generate_insights(timesteps, 1.5, "audio", _reference()) == []
    timesteps[2]["regions"]["auditory"] = 0.9
    timesteps[2]["time_sec"] = 20.0
    assert generate_insights(timesteps, 1.5, "audio", _reference()) == []


def test_registry_modalities_match_region_inputs():
    from app.services.brain_regions import REGION_MODALITIES
    from app.services.insight_rules import DETECTORS, INPUT_MODALITIES

    for detector in DETECTORS:
        for media_type in detector.modalities:
            assert INPUT_MODALITIES[media_type] & set(REGION_MODALITIES[detector.signal]), detector.id


def test_inferential_detectors_are_disabled_without_outcome_calibration(monkeypatch):
    from app.services import insight_rules

    speculative = insight_rules.Detector(
        "predicted_recall", "auditory", "above_reference", ("audio",),
        "inferential", "This ad will be remembered", "unvalidated",
    )
    monkeypatch.setattr(insight_rules, "DETECTORS", insight_rules.DETECTORS + (speculative,))
    timesteps = _make_timesteps(4, {"auditory": [0.9]})
    assert all(item["type"] != "predicted_recall" for item in generate_insights(timesteps, 1.5, "audio", _reference()))
