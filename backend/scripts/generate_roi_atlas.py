#!/usr/bin/env python3
"""Generate a JSON atlas mapping each fsaverage5 vertex to its HCP-MMP1 ROI.

Output: backend/static/atlas/hcp_atlas.json
Structure:
{
  "lh": ["V1", "V1", "V2", ...],           // 10242 entries
  "rh": ["V1", "V1", "V2", ...],           // 10242 entries
  "roi_info": {
    "V1": { "full_name": "Primary Visual Cortex", "category": "visual" },
    ...
  }
}
"""

import json
import sys
from pathlib import Path

# Ensure tribev2 and the app package are importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".."))  # project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".." / "tribev2"))  # vendored tribev2

from tribev2.utils import get_hcp_labels

# Functional categories from brain_regions.py — single source of
# truth so the atlas and the API can never drift apart.
from app.services.brain_regions import REGION_GROUPS
from app.config import settings

# Human-readable names for common HCP-MMP1 ROIs
ROI_FULL_NAMES: dict[str, str] = {
    "V1": "Primary Visual Cortex",
    "V2": "Secondary Visual Cortex",
    "V3": "Third Visual Area",
    "V3A": "Visual Area V3A",
    "V3B": "Visual Area V3B",
    "V3CD": "Visual Area V3CD",
    "V4": "Visual Area V4",
    "V4t": "Extriastriate Body Area (EBA)",
    "V6": "Visual Area V6",
    "V6A": "Visual Area V6A",
    "V7": "Visual Area V7",
    "V8": "Visual Area V8",
    "MT": "Middle Temporal Visual Area",
    "MST": "Medial Superior Temporal Area",
    "FST": "Fundus of Superior Temporal Sulcus",
    "PH": "Parahippocampal Place Area (PPA)",
    "LO1": "Lateral Occipital Area 1",
    "LO2": "Lateral Occipital Area 2",
    "LO3": "Lateral Occipital Area 3",
    "PIT": "Posterior Infero-Temporal Area",
    "FFC": "Fusiform Face Complex (FFA)",
    "VMV1": "Ventromedial Visual Area 1",
    "VMV2": "Ventromedial Visual Area 2",
    "VMV3": "Ventromedial Visual Area 3",
    "VVC": "Ventral Visual Complex",
    "PHA1": "Parahippocampal Area 1",
    "PHA2": "Parahippocampal Area 2",
    "PHA3": "Parahippocampal Area 3",
    "A1": "Primary Auditory Cortex",
    "A4": "Auditory Area 4",
    "A5": "Auditory Area 5",
    "LBelt": "Lateral Belt",
    "MBelt": "Medial Belt",
    "PBelt": "Parabelt",
    "RI": "Retroinsular Cortex",
    "TA2": "Temporal Area 2",
    "STSdp": "Superior Temporal Sulcus (dorsal posterior)",
    "STSda": "Superior Temporal Sulcus (dorsal anterior)",
    "STSvp": "Superior Temporal Sulcus (ventral posterior)",
    "STSva": "Superior Temporal Sulcus (ventral anterior)",
    "44": "Broca's Area (Pars Opercularis)",
    "45": "Broca's Area (Pars Triangularis)",
    "47l": "Inferior Frontal Area 47l",
    "47s": "Inferior Frontal Area 47s",
    "STV": "Superior Temporal Visual Area",
    "PSL": "Perisylvian Language Area",
    "TPOJ1": "Temporo-Parieto-Occipital Junction 1",
    "TPOJ2": "Temporo-Parieto-Occipital Junction 2",
    "TPOJ3": "Temporo-Parieto-Occipital Junction 3",
    "SFL": "Superior Frontal Language Area",
    "55b": "Area 55b",
    "IFSa": "Inferior Frontal Sulcus (anterior)",
    "IFSp": "Inferior Frontal Sulcus (posterior)",
    "IFJa": "Inferior Frontal Junction (anterior)",
    "IFJp": "Inferior Frontal Junction (posterior)",
    "8Av": "Frontal Eye Field Area 8Av",
    "8BL": "Frontal Area 8BL",
    "8Ad": "Frontal Area 8Ad",
    "8C": "Frontal Area 8C",
    "9m": "Medial Prefrontal Area 9m",
    "9p": "Posterior Prefrontal Area 9p",
    "9a": "Anterior Prefrontal Area 9a",
    "10d": "Dorsal Prefrontal Area 10d",
    "10r": "Rostral Prefrontal Area 10r",
    "10v": "Ventral Prefrontal Area 10v",
    "10pp": "Polar Prefrontal Area 10pp",
    "46": "Dorsolateral Prefrontal Cortex (Area 46)",
    "a47r": "Anterior Area 47r",
    "p47r": "Posterior Area 47r",
    "FEF": "Frontal Eye Fields",
    "PEF": "Premotor Eye Fields",
    "6ma": "Supplementary Motor Area (anterior)",
    "6mp": "Supplementary Motor Area (posterior)",
    "6d": "Dorsal Premotor Cortex",
    "6v": "Ventral Premotor Cortex",
    "6r": "Rostral Premotor Cortex",
    "a9-46v": "Anterior Area 9-46v",
    "p9-46v": "Posterior Area 9-46v",
    "a10p": "Anterior Area 10p",
    "p10p": "Posterior Area 10p",
    "PGi": "Inferior Parietal Area PGi",
    "PGs": "Superior Parietal Area PGs",
    "PFm": "Parietal Area PFm",
    "1": "Primary Somatosensory Area 1",
    "2": "Somatosensory Area 2",
    "3a": "Somatosensory Area 3a",
    "3b": "Primary Somatosensory Area 3b",
    "4": "Primary Motor Cortex",
    "5L": "Superior Parietal Area 5L",
    "5m": "Medial Parietal Area 5m",
    "5mv": "Medioventral Area 5",
    "7AL": "Superior Parietal Area 7AL",
    "7Am": "Medial Area 7A",
    "7PC": "Postcentral Area 7PC",
    "7PL": "Lateral Parietal Area 7PL",
    "7Pm": "Medial Parietal Area 7Pm",
    "23c": "Posterior Cingulate Area 23c",
    "23d": "Posterior Cingulate Area 23d",
    "24dd": "Cingulate Area 24dd",
    "24dv": "Cingulate Area 24dv",
    "25": "Subgenual Cortex",
    "31a": "Cingulate Area 31a",
    "31pd": "Cingulate Area 31pd",
    "31pv": "Cingulate Area 31pv",
    "33pr": "Cingulate Area 33pr",
    "AIP": "Anterior Intraparietal Area",
    "AVI": "Anterior Ventral Insular Area",
    "d23ab": "Dorsal Posterior Cingulate 23ab",
    "d32": "Dorsal Area 32",
    "DVT": "Dorsal Visual Transitional Area",
    "EC": "Entorhinal Cortex",
    "FOP1": "Frontal Opercular Area 1",
    "FOP2": "Frontal Opercular Area 2",
    "FOP3": "Frontal Opercular Area 3",
    "FOP4": "Frontal Opercular Area 4",
    "FOP5": "Frontal Opercular Area 5",
    "Ig": "Granular Insula",
    "IP0": "Intraparietal Area 0",
    "IP1": "Intraparietal Area 1",
    "IP2": "Intraparietal Area 2",
    "LIPd": "Lateral Intraparietal (dorsal)",
    "LIPv": "Lateral Intraparietal (ventral)",
    "MIP": "Medial Intraparietal Area",
    "MI": "Middle Insular Area",
    "OFC": "Orbitofrontal Cortex",
    "OP1": "Parietal Operculum 1",
    "OP2-3": "Parietal Operculum 2-3",
    "OP4": "Parietal Operculum 4",
    "p24": "Pregenual Cingulate 24",
    "p24pr": "Pregenual Cingulate 24pr",
    "p32": "Pregenual Area 32",
    "p32pr": "Pregenual Area 32pr",
    "PBr": "Parietal Area PBr (Broca's homolog)",
    "PCV": "Precuneus Visual Area",
    "PeEc": "Perirhinal Ectorhinal Cortex",
    "PF": "Parietal Area PF",
    "PFcm": "Parietal Area PFcm",
    "PFop": "Parietal Opercular Area PFop",
    "PFt": "Parietal Area PFt",
    "PGp": "Parietal Area PGp",
    "PHA1": "Parahippocampal Area 1",
    "PI": "Para-Insular Area",
    "Pol1": "Polar Area 1",
    "Pol2": "Polar Area 2",
    "PreS": "Presubiculum",
    "ProS": "Prosubiculum",
    "pOFC": "Posterior Orbitofrontal Cortex",
    "RSC": "Retrosplenial Cortex",
    "s6-8": "Supplementary Area s6-8",
    "s32": "Subgenual Area 32",
    "STS": "Superior Temporal Sulcus",
    "STGa": "Superior Temporal Gyrus (anterior)",
    "TE1a": "Middle Temporal Gyrus (MTG)",
    "TE1m": "Temporal Area TE1m",
    "TE1p": "Temporal Area TE1p",
    "TE2a": "Temporal Area TE2a",
    "TE2p": "Temporal Area TE2p",
    "TF": "Temporal Fusiform Area",
    "TGd": "Temporal Gyrus (dorsal)",
    "TGv": "Temporal Gyrus (ventral)",
    "v23ab": "Ventral Posterior Cingulate 23ab",
}


def roi_category(roi_name: str) -> str:
    """Return the functional category for a given ROI name."""
    for cat, rois in REGION_GROUPS.items():
        if roi_name in rois:
            return cat
    return "other"


def main():
    out_dir = settings.static_dir / "atlas"
    out_dir.mkdir(parents=True, exist_ok=True)

    n_vert = 10242  # fsaverage5 per hemisphere

    # Build per-hemisphere vertex→ROI arrays
    lh_labels = get_hcp_labels(mesh="fsaverage5", combine=False, hemi="left")
    rh_labels = get_hcp_labels(mesh="fsaverage5", combine=False, hemi="right")

    lh_map = [""] * n_vert
    for roi_name, vertices in lh_labels.items():
        for v in vertices:
            if v < n_vert:
                lh_map[v] = roi_name

    rh_map = [""] * n_vert
    for roi_name, vertices in rh_labels.items():
        # rh vertices are offset by n_vert in the combined array
        for v in vertices:
            idx = v - n_vert
            if 0 <= idx < n_vert:
                rh_map[idx] = roi_name

    # Build ROI info dictionary
    all_rois = sorted(set(lh_map + rh_map) - {""})
    roi_info = {}
    for roi in all_rois:
        roi_info[roi] = {
            "full_name": ROI_FULL_NAMES.get(roi, roi),
            "category": roi_category(roi),
        }

    atlas = {
        "lh": lh_map,
        "rh": rh_map,
        "roi_info": roi_info,
    }

    out_path = out_dir / "hcp_atlas.json"
    with open(out_path, "w") as f:
        json.dump(atlas, f, separators=(",", ":"))

    # Stats
    labeled_lh = sum(1 for x in lh_map if x)
    labeled_rh = sum(1 for x in rh_map if x)
    print(f"Atlas generated: {out_path}")
    print(f"  LH: {labeled_lh}/{n_vert} vertices labeled ({len(set(lh_map) - {''})} ROIs)")
    print(f"  RH: {labeled_rh}/{n_vert} vertices labeled ({len(set(rh_map) - {''})} ROIs)")
    print(f"  ROI info: {len(roi_info)} entries")
    print(f"  File size: {out_path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
