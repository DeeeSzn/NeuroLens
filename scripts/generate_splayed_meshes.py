#!/usr/bin/env python3
"""
Generate "splayed" (open-book) mesh files for NiiVue.

For each hemisphere pair (pial and inflated):
  1. Rotate the left hemisphere +90° around the Z-axis (vertical).
  2. Rotate the right hemisphere -90° around the Z-axis.
  3. Compute bounding boxes AFTER rotation and place each hemisphere
     so they sit side-by-side with a gap between them — left hemi on
     the left, right hemi on the right.

The resulting meshes can be loaded in a single NiiVue instance with
camera azimuth=0 (straight-on) to show the medial surfaces of both
hemispheres simultaneously — the TRIBEv2 "Open" view.
"""

import argparse
import os
import sys
import numpy as np
import nibabel as nib

# ── Configuration ────────────────────────────────────────────────────────────
MESH_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "frontend",
    "public",
    "static",
    "meshes",
)

GAP_MM = 10  # mm of empty space between the two hemispheres

# Pairs: (input_left, input_right, output_left, output_right)
PAIRS = [
    ("pial_left.gii", "pial_right.gii", "pial_left_open.gii", "pial_right_open.gii"),
    ("infl_left.gii", "infl_right.gii", "infl_left_open.gii", "infl_right_open.gii"),
]


def rotation_z(degrees: float) -> np.ndarray:
    """3×3 rotation matrix around the Z-axis."""
    rad = np.radians(degrees)
    c, s = np.cos(rad), np.sin(rad)
    return np.array([
        [c, -s, 0],
        [s,  c, 0],
        [0,  0, 1],
    ])


def load_and_rotate(path: str, angle_deg: float) -> tuple:
    """Load GIFTI, rotate coords, return (gii_obj, rotated_coords)."""
    gii = nib.load(path)
    coords = gii.darrays[0].data.copy()  # (N, 3) float32
    assert coords.ndim == 2 and coords.shape[1] == 3
    R = rotation_z(angle_deg).astype(np.float32)
    coords = coords @ R.T
    return gii, coords


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh-dir", default=MESH_DIR)
    args = parser.parse_args()
    mesh_dir = os.path.normpath(args.mesh_dir)
    print(f"Mesh directory: {mesh_dir}\n")

    for lf, rf, lo, ro in PAIRS:
        left_in = os.path.join(mesh_dir, lf)
        right_in = os.path.join(mesh_dir, rf)
        left_out = os.path.join(mesh_dir, lo)
        right_out = os.path.join(mesh_dir, ro)

        for f in (left_in, right_in):
            if not os.path.isfile(f):
                print(f"ERROR: source file not found: {f}", file=sys.stderr)
                sys.exit(1)

        print(f"Processing {lf} / {rf}:")

        # 1. Rotate — +90 for left, -90 for right so the medial
        #    (inner) surfaces face the camera at azimuth=0
        gii_l, coords_l = load_and_rotate(left_in, +90)
        gii_r, coords_r = load_and_rotate(right_in, -90)

        # 2. Compute X bounding boxes after rotation
        l_xmin, l_xmax = coords_l[:, 0].min(), coords_l[:, 0].max()
        r_xmin, r_xmax = coords_r[:, 0].min(), coords_r[:, 0].max()
        l_width = l_xmax - l_xmin
        r_width = r_xmax - r_xmin

        print(f"  Left  rotated X: [{l_xmin:.1f}, {l_xmax:.1f}]  width={l_width:.1f}")
        print(f"  Right rotated X: [{r_xmin:.1f}, {r_xmax:.1f}]  width={r_width:.1f}")

        # 3. Place left hemisphere to the left, right hemisphere to the right
        #    Left hemi: shift so its right edge sits at x = -GAP/2
        #    Right hemi: shift so its left edge sits at x = +GAP/2
        left_shift = -(GAP_MM / 2) - l_xmax
        right_shift = (GAP_MM / 2) - r_xmin

        coords_l[:, 0] += left_shift
        coords_r[:, 0] += right_shift

        print(f"  Left  shift: {left_shift:+.1f}  →  X: [{coords_l[:,0].min():.1f}, {coords_l[:,0].max():.1f}]")
        print(f"  Right shift: {right_shift:+.1f}  →  X: [{coords_r[:,0].min():.1f}, {coords_r[:,0].max():.1f}]")

        # 4. Write output
        gii_l.darrays[0].data = coords_l
        nib.save(gii_l, left_out)
        print(f"  ✓ {os.path.basename(left_out)}")

        gii_r.darrays[0].data = coords_r
        nib.save(gii_r, right_out)
        print(f"  ✓ {os.path.basename(right_out)}")
        print()

    print("Done — splayed meshes written.")


if __name__ == "__main__":
    main()
