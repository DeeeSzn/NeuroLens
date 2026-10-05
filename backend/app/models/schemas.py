"""Pydantic schemas for API request/response models."""

from typing import List, Optional

from pydantic import BaseModel


class JobCreateResponse(BaseModel):
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    filename: str
    media_type: str
    created_at: str
    error_message: Optional[str] = None


class RegionActivation(BaseModel):
    visual: float
    auditory: float
    language: float
    multisensory: float
    # Prefrontal split — defaults keep results saved before the
    # split loadable (they carry the old "prefrontal" key instead).
    dorsal_attention: float = 0.0
    mpfc_valuation: float = 0.0
    # Paper-grounded named regions (TRIBE v2, section 5.9)
    tpoj: float = 0.0       # temporal-parietal-occipital junction (peak multimodal site)
    memory: float = 0.0     # parahippocampal (PPA) + middle temporal gyrus
    face_body: float = 0.0  # fusiform face complex (FFA) + extrastriate body area (EBA)


class TimestepData(BaseModel):
    time_sec: float
    regions: RegionActivation
    top_rois: List[str]
    words: List[str]


class AnalysisResult(BaseModel):
    job_id: str
    filename: str
    media_type: str
    duration_sec: float
    n_timesteps: int
    tr_seconds: float
    timesteps: List[TimestepData]


class BrainTimestepData(BaseModel):
    timestep: int
    time_sec: float
    vertices: List[float]
    regions: RegionActivation


class TimelineData(BaseModel):
    job_id: str
    tr_seconds: float
    times: List[float]
    visual: List[float]
    auditory: List[float]
    language: List[float]
    multisensory: List[float]
    dorsal_attention: List[float] = []
    mpfc_valuation: List[float] = []
    tpoj: List[float] = []
    memory: List[float] = []
    face_body: List[float] = []


class Insight(BaseModel):
    time_start: float
    time_end: float
    type: str
    severity: Optional[float] = None
    region: str
    description: str
    value: Optional[float] = None
    reference: Optional[dict] = None
    z: Optional[float] = None
    evidence_rois: List[str] = []
    claim_level: Optional[str] = None
    confidence: Optional[float] = None
    caveat: Optional[str] = None
    ruleset_version: Optional[str] = None
    citation: Optional[str] = None


class InsightsResponse(BaseModel):
    job_id: str
    insights: List[Insight]
    reference_status: str = "unavailable"
    reference_version: Optional[str] = None


class ComparisonDelta(BaseModel):
    time_sec: float
    visual_delta: float
    auditory_delta: float
    language_delta: float
    multisensory_delta: float
    dorsal_attention_delta: float = 0.0
    mpfc_valuation_delta: float = 0.0
    tpoj_delta: float = 0.0
    memory_delta: float = 0.0
    face_body_delta: float = 0.0


class ComparisonResult(BaseModel):
    job_a_id: str
    job_b_id: str
    summary: str
    deltas: List[ComparisonDelta]
    insights: List[str]
