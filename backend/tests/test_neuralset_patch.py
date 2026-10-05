from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from apply_neuralset_mps import AUTO_ORIGINAL, AUTO_PATCHED, patch_source


@pytest.mark.parametrize("filename,device", [
    ("base.py", 'tp.Literal["auto", "cpu", "cuda", "accelerate"]'),
    ("video.py", 'tp.Literal["auto", "cpu", "cuda"]'),
])
def test_patch_is_idempotent(filename, device):
    source = f"device: {device}\n{AUTO_ORIGINAL}\n"
    patched = patch_source(source, filename)
    assert '"mps"' in patched
    assert AUTO_PATCHED in patched
    assert patch_source(patched, filename) == patched


def test_unknown_source_fails_without_silent_fallback():
    with pytest.raises(ValueError, match="Unrecognized"):
        patch_source("device: str\n", "base.py")
