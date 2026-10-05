#!/usr/bin/env python3
"""Prepare visualization assets locally; no atlas or mesh data is distributed."""

import argparse
from pathlib import Path
import subprocess
import sys

MESH_NAMES = ("pial_left", "pial_right", "infl_left", "infl_right")


def write_meshes(source: dict[str, str], destination: Path) -> None:
    import nibabel as nib

    destination.mkdir(parents=True, exist_ok=True)
    for name in MESH_NAMES:
        target = destination / f"{name}.gii"
        nib.save(nib.load(source[name]), target)
        print(f"Prepared {target}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--accept-data-terms", action="store_true",
        help="Confirm that you have reviewed HCP and FreeSurfer/fsaverage terms for your use",
    )
    args = parser.parse_args()
    if not args.accept_data_terms:
        parser.error(
            "Review HCP Open Access Data Use Terms and FreeSurfer/fsaverage terms first; "
            "then pass --accept-data-terms. See THIRD_PARTY_NOTICES.md. "
            "This is not permission to redistribute generated assets."
        )

    backend = Path(__file__).resolve().parents[1]
    project = backend.parent
    sys.path.insert(0, str(backend))
    from app.config import settings
    from nilearn.datasets import fetch_surf_fsaverage

    mesh_dir = settings.static_dir / "meshes"
    write_meshes(fetch_surf_fsaverage(mesh="fsaverage5"), mesh_dir)
    subprocess.run([
        sys.executable, str(project / "scripts/generate_splayed_meshes.py"),
        "--mesh-dir", str(mesh_dir),
    ], check=True)
    subprocess.run([
        sys.executable, str(backend / "scripts/generate_roi_atlas.py"),
    ], check=True)
    print(f"Visualization assets ready in {settings.static_dir}")


if __name__ == "__main__":
    main()
