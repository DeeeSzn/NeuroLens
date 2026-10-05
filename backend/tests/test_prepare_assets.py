import importlib.util
from pathlib import Path
import subprocess
import sys

import nibabel as nib
import numpy as np

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/prepare_assets.py"
SPEC = importlib.util.spec_from_file_location("prepare_assets", SCRIPT)
assets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assets)


def test_requires_explicit_terms_confirmation_before_loading_dependencies():
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 2
    assert "--accept-data-terms" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr


def test_writes_valid_mesh_arrays_without_changing_geometry(tmp_path):
    coordinates = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
    triangles = np.array([[0, 1, 2]], dtype=np.int32)
    mesh = nib.gifti.GiftiImage(darrays=[
        nib.gifti.GiftiDataArray(coordinates, intent="NIFTI_INTENT_POINTSET"),
        nib.gifti.GiftiDataArray(triangles, intent="NIFTI_INTENT_TRIANGLE"),
    ])
    source = tmp_path / "source.gii.gz"
    nib.save(mesh, source)
    destination = tmp_path / "meshes"
    assets.write_meshes({name: str(source) for name in assets.MESH_NAMES}, destination)
    for name in assets.MESH_NAMES:
        loaded = nib.load(destination / f"{name}.gii")
        np.testing.assert_array_equal(loaded.darrays[0].data, coordinates)
        np.testing.assert_array_equal(loaded.darrays[1].data, triangles)


def test_open_mesh_command_writes_into_selected_directory(tmp_path):
    coordinates = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
    triangles = np.array([[0, 1, 2]], dtype=np.int32)
    mesh = nib.gifti.GiftiImage(darrays=[
        nib.gifti.GiftiDataArray(coordinates, intent="NIFTI_INTENT_POINTSET"),
        nib.gifti.GiftiDataArray(triangles, intent="NIFTI_INTENT_TRIANGLE"),
    ])
    for name in assets.MESH_NAMES:
        nib.save(mesh, tmp_path / f"{name}.gii")
    script = SCRIPT.parents[2] / "scripts/generate_splayed_meshes.py"
    subprocess.run([sys.executable, str(script), "--mesh-dir", str(tmp_path)], check=True)
    for name in assets.MESH_NAMES:
        loaded = nib.load(tmp_path / f"{name}_open.gii")
        np.testing.assert_array_equal(loaded.darrays[1].data, triangles)
    left = nib.load(tmp_path / "pial_left_open.gii").darrays[0].data
    right = nib.load(tmp_path / "pial_right_open.gii").darrays[0].data
    assert np.isclose(right[:, 0].min() - left[:, 0].max(), 10)
