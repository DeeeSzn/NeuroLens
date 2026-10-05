"""Brain region mapping using HCP-MMP1 parcellation.

Groups HCP ROIs into functional categories for high-level reporting.

The partition is STRICT: every ROI belongs to exactly one region, so
activation series never double-count a parcel. Regions are ordered by
stream (sensory -> association -> named hubs).

ROI labels for named regions (from TRIBE v2 paper, section 5.9, Glasser
parcellation):
  FFA (fusiform face area)    -> FFC      (face_body)
  EBA (extrastriate body)     -> V4t      (face_body)
  PPA (parahippocampal place) -> PH       (memory)
  VWFA (visual word form)     -> A5       (auditory)
  TPJ (temporo-parietal jct)  -> PGi      (multisensory)
  MTG (middle temporal gyrus) -> TE1a     (memory)
  TPOJ (TP-occipital jct)     -> TPOJ1/2/3 (tpoj)

Note: the STS family (STSvp/STSva/STSdp/STSda) is deliberately NOT
grouped — those parcels sit between auditory and multisensory and were
previously double-counted in both.
"""

# HCP-MMP1 ROI names grouped by functional category.
# Prefixes L_ / R_ are added dynamically for hemisphere-specific lookups.

REGION_GROUPS: dict[str, list[str]] = {
    # --- Sensory streams (each ROI in exactly one region) ---
    "visual": [
        "V1", "V2", "V3", "V3A", "V3B", "V3CD", "V4", "V6", "V6A",
        "V7", "V8", "VMV1", "VMV2", "VMV3", "VVC", "PHA1", "PHA2",
        "PHA3", "MT", "MST", "FST", "LO1", "LO2", "LO3", "PIT",
        # face/body (FFC, V4t) and place (PH) parcels live in their
        # own named regions below, not here.
    ],
    "auditory": [
        "A1", "A4", "A5", "LBelt", "MBelt", "PBelt", "RI", "TA2",
    ],
    "language": [
        "44", "45", "47l", "47s", "STV", "PSL", "SFL", "55b",
        "IFSa", "IFSp", "IFJa", "IFJp",
        # TPOJ1/2/3 moved to the tpoj region.
    ],
    # --- Prefrontal split (old "prefrontal" group, disjoint halves) ---
    # Dorsal attention: frontal components of the oculomotor /
    # attention-control network (area 8, premotor area 6, FEF, PEF).
    "dorsal_attention": [
        "8Av", "8BL", "8Ad", "8C",
        "FEF", "PEF",
        "6ma", "6mp", "6d", "6v", "6r",
    ],
    # mPFC / valuation: medial prefrontal (area 9), frontal pole
    # (area 10), dorsolateral executive (area 46, 9/46v) and ventral
    # area 47r — the regions that track engagement and value.
    "mpfc_valuation": [
        "9m", "9p", "9a",
        "10d", "10r", "10v", "10pp",
        "46", "a47r", "p47r",
        "a9-46v", "p9-46v",
        "a10p", "p10p",
    ],
    # --- Heteromodal association ---
    # Inferior parietal (angular/supramarginal): the classic
    # multisensory convergence zone.
    "multisensory": [
        "PGi", "PGs", "PFm",
    ],
    # --- Paper-grounded named regions (TRIBE v2, section 5.9) ---
    # Temporal-parietal-occipital junction: the paper's peak multimodal
    # integration site — up to 50% encoding gain over any single modality.
    "tpoj": [
        "TPOJ1", "TPOJ2", "TPOJ3",
    ],
    # Memory-relevant cortical regions: parahippocampal place area
    # (PH=PPA) and middle temporal gyrus (TE1a=MTG). Hippocampus itself
    # is subcortical and not in the released cortical-only checkpoint.
    "memory": [
        "PH",    # parahippocampal place area — scene/spatial/memory encoding
        "TE1a",  # middle temporal gyrus — semantic memory and language
        "TF",    # temporal fusiform — object recognition and memory consolidation
    ],
    # Face and body content detection: fusiform face complex (FFC=FFA) and
    # V4t (EBA=extrastriate body area), from paper's in-silico visual experiments.
    "face_body": [
        "FFC",   # fusiform face complex — face-selective (FFA)
        "V4t",   # extrastriate body area — body-selective (EBA)
    ],
}

# Input modalities whose TRIBE v2 features drive each region
# ("video" = V-JEPA2, "audio" = Wav2Vec-BERT, "text" = LLaMA transcript).
# Supramodal regions list all three.
REGION_MODALITIES: dict[str, list[str]] = {
    "visual": ["video"],
    "auditory": ["audio"],
    "language": ["audio", "text"],
    "dorsal_attention": ["video", "audio", "text"],
    "mpfc_valuation": ["video", "audio", "text"],
    "multisensory": ["video", "audio", "text"],
    "tpoj": ["video", "audio", "text"],
    "memory": ["video", "audio", "text"],
    "face_body": ["video"],
}

# Canonical ordering of all region groups. Backend consumers (timeline,
# comparison, export) should iterate this instead of hardcoding lists, so a
# new region cannot silently disappear from one endpoint.
REGION_ORDER: list[str] = list(REGION_GROUPS)


def get_region_roi_names(region: str, hemi: str = "both") -> list[str]:
    """Return full ROI names (with hemisphere prefix) for a region group."""
    base_names = REGION_GROUPS.get(region, [])
    names = []
    if hemi in ("left", "both"):
        names.extend(f"L_{n}" for n in base_names)
    if hemi in ("right", "both"):
        names.extend(f"R_{n}" for n in base_names)
    return names
