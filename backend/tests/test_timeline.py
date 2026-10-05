"""Tests for timeline series construction (all regions + legacy results)."""

from app.routers.analysis import timeline_series
from app.services.brain_regions import REGION_ORDER

# Results saved before the prefrontal split carry these keys.
LEGACY_REGIONS = ["visual", "auditory", "language", "prefrontal", "multisensory"]


def _ts(regions):
    return {"time_sec": 0.0, "regions": regions, "top_rois": [], "words": []}


def test_all_regions_present():
    series = timeline_series([_ts({r: 0.5 for r in REGION_ORDER})])
    assert set(series) == set(REGION_ORDER)
    assert all(values == [0.5] for values in series.values())


def test_legacy_five_key_result_defaults_to_zero():
    legacy = {r: 0.5 for r in LEGACY_REGIONS}
    series = timeline_series([_ts(legacy)])
    assert series["visual"] == [0.5]
    assert series["multisensory"] == [0.5]
    # Split regions and named regions did not exist yet → 0.0
    assert series["dorsal_attention"] == [0.0]
    assert series["mpfc_valuation"] == [0.0]
    assert series["tpoj"] == [0.0]
    assert series["memory"] == [0.0]
    assert series["face_body"] == [0.0]


def test_empty_timesteps():
    series = timeline_series([])
    assert set(series) == set(REGION_ORDER)
    assert all(values == [] for values in series.values())
