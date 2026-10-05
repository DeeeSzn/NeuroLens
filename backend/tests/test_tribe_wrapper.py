"""Tests for the inference wrapper's normalization (no model load)."""

import numpy as np

from app.services.tribe_wrapper import _robust_normalize


def test_normalizes_to_unit_range():
    out = _robust_normalize(np.linspace(-5, 5, 1000))
    assert out.min() >= 0.0
    assert out.max() <= 1.0
    assert out.max() == 1.0  # values at/above the 99th percentile clip to 1


def test_constant_array_returns_zeros():
    out = _robust_normalize(np.full((3, 4), 2.0))
    assert np.all(out == 0.0)


def test_nan_and_inf_do_not_leak():
    arr = np.array([np.nan, np.inf, -np.inf, 1.0, 2.0, 3.0])
    out = _robust_normalize(arr)
    assert np.isfinite(out).all()
    assert out.min() >= 0.0 and out.max() <= 1.0


def test_preserves_shape():
    arr = np.random.default_rng(0).normal(size=(5, 64)).astype(np.float32)
    out = _robust_normalize(arr)
    assert out.shape == arr.shape
