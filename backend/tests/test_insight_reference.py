"""Pilot reference integrity and source-isolated comparisons."""

import numpy as np
import pytest

from app.services.insight_reference import build_reference, current_timesteps, region_reference


def _result(value: float) -> dict:
    return {
        "timesteps": [{"time_sec": float(time), "regions": {"visual": 0}, "words": [], "top_rois": []} for time in range(3)],
        "raw_vertices": [[value, value]] * 3,
    }


def test_reaggregates_old_regions_from_saved_vertices(monkeypatch):
    monkeypatch.setattr("app.services.insight_reference._get_hcp_label_map", lambda: {"V1": np.array([0]), "A1": np.array([1])})
    timesteps = current_timesteps(_result(0.7))
    assert timesteps[0]["regions"]["visual"] == pytest.approx(0.7)
    assert timesteps[0]["regions"]["auditory"] == pytest.approx(0.7)
    assert "dorsal_attention" in timesteps[0]["regions"]
    assert timesteps[1]["time_sec"] == 1.0


def test_reference_rejects_duplicate_or_short_sources(monkeypatch):
    monkeypatch.setattr("app.services.insight_reference._get_hcp_label_map", lambda: {"V1": np.array([0])})
    with pytest.raises(ValueError, match="Duplicate source"):
        build_reference([("same", _result(0.2)), ("same", _result(0.4))], "audio")
    with pytest.raises(ValueError, match="three timesteps"):
        build_reference([("short", {"timesteps": [{}], "raw_vertices": [[0.1, 0.1]]})], "audio")


def test_source_is_excluded_from_reference_distribution():
    reference = {
        "clips": {
            "target": {"regions": {"auditory": {"mean": 0.9, "variance": 0.01}}},
            "other-a": {"regions": {"auditory": {"mean": 0.2, "variance": 0.01}}},
            "other-b": {"regions": {"auditory": {"mean": 0.4, "variance": 0.01}}},
        }
    }
    baseline = region_reference(reference, "auditory", "target")
    assert baseline["n_clips"] == 2
    assert baseline["mean"] == pytest.approx(0.3)
    assert baseline["std"] == pytest.approx(np.sqrt(0.02))
    assert region_reference({"clips": {"target": reference["clips"]["target"], "other-a": reference["clips"]["other-a"]}}, "auditory", "target") is None