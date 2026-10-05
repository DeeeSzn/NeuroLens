/** API client for NeuroLens backend. */

const API_BASE = "/api";

export interface JobStatus {
  job_id: string;
  status: "pending" | "processing" | "complete" | "failed";
  progress: number;
  filename: string;
  media_type: string;
  created_at: string;
  error_message: string | null;
}

export interface RegionActivation {
  visual: number;
  auditory: number;
  language: number;
  multisensory: number;
  /** Prefrontal split — absent from results saved before the split. */
  dorsal_attention?: number;
  mpfc_valuation?: number;
  tpoj?: number;
  memory?: number;
  face_body?: number;
}

export interface TimestepData {
  time_sec: number;
  regions: RegionActivation;
  top_rois: string[];
  words: string[];
}

export interface AnalysisResult {
  job_id: string;
  filename: string;
  media_type: string;
  duration_sec: number;
  n_timesteps: number;
  tr_seconds: number;
  timesteps: TimestepData[];
}

export interface TimelineData {
  job_id: string;
  tr_seconds: number;
  times: number[];
  visual: number[];
  auditory: number[];
  language: number[];
  multisensory: number[];
  dorsal_attention?: number[];
  mpfc_valuation?: number[];
  tpoj?: number[];
  memory?: number[];
  face_body?: number[];
}

export interface BrainTimestepData {
  timestep: number;
  time_sec: number;
  vertices: number[];
  regions: RegionActivation;
}

export interface Insight {
  time_start: number;
  time_end: number;
  type: string;
  severity?: number | null;
  region: string;
  description: string;
  value?: number | null;
  reference?: { mean: number; std: number; n_clips: number } | null;
  z?: number | null;
  evidence_rois?: string[];
  claim_level?: "descriptive" | "inferential" | null;
  confidence?: number | null;
  caveat?: string | null;
  ruleset_version?: string | null;
  citation?: string | null;
}

export interface InsightsResponse {
  job_id: string;
  insights: Insight[];
  reference_status: "exploratory" | "unavailable";
  reference_version: string | null;
}

export interface AllVerticesData {
  n_timesteps: number;
  n_vertices: number;
  vertices: number[][];
}

export interface ComparisonResult {
  job_a_id: string;
  job_b_id: string;
  summary: string;
  deltas: {
    time_sec: number;
    visual_delta: number;
    auditory_delta: number;
    language_delta: number;
    multisensory_delta: number;
    dorsal_attention_delta?: number;
    mpfc_valuation_delta?: number;
    tpoj_delta?: number;
    memory_delta?: number;
    face_body_delta?: number;
  }[];
  insights: string[];
}

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json();
}

export const api = {
  async uploadFile(file: File): Promise<{ job_id: string }> {
    const form = new FormData();
    form.append("file", file);
    return fetchJSON(`${API_BASE}/analyze`, { method: "POST", body: form });
  },

  getJobStatus(jobId: string): Promise<JobStatus> {
    return fetchJSON(`${API_BASE}/jobs/${encodeURIComponent(jobId)}`);
  },

  listJobs(): Promise<JobStatus[]> {
    return fetchJSON(`${API_BASE}/jobs`);
  },

  getResult(jobId: string): Promise<AnalysisResult> {
    return fetchJSON(`${API_BASE}/jobs/${encodeURIComponent(jobId)}/result`);
  },

  getTimeline(jobId: string): Promise<TimelineData> {
    return fetchJSON(`${API_BASE}/jobs/${encodeURIComponent(jobId)}/timeline`);
  },

  getBrainTimestep(jobId: string, timestep: number): Promise<BrainTimestepData> {
    return fetchJSON(`${API_BASE}/jobs/${encodeURIComponent(jobId)}/brain/${timestep}`);
  },

  getInsights(jobId: string): Promise<InsightsResponse> {
    return fetchJSON(`${API_BASE}/jobs/${encodeURIComponent(jobId)}/insights`);
  },

  getAllVertices(jobId: string): Promise<AllVerticesData> {
    return fetchJSON(`${API_BASE}/jobs/${encodeURIComponent(jobId)}/all-vertices`);
  },

  compare(jobAId: string, jobBId: string): Promise<ComparisonResult> {
    return fetchJSON(
      `${API_BASE}/compare/${encodeURIComponent(jobAId)}/${encodeURIComponent(jobBId)}`
    );
  },

  /** Cooperative cancel — takes effect at the next inference checkpoint. */
  cancelJob(jobId: string): Promise<{ job_id: string; status: string }> {
    return fetchJSON(`${API_BASE}/jobs/${encodeURIComponent(jobId)}/cancel`, {
      method: "POST",
    });
  },

  /** Re-queue a failed job, reusing the original upload. */
  retryJob(jobId: string): Promise<{ job_id: string; status: string }> {
    return fetchJSON(`${API_BASE}/jobs/${encodeURIComponent(jobId)}/retry`, {
      method: "POST",
    });
  },
};

/** Download URLs for a completed analysis (server sets Content-Disposition). */
export const exportUrls = {
  report: (jobId: string) =>
    `${API_BASE}/jobs/${encodeURIComponent(jobId)}/export/report`,
  json: (jobId: string) =>
    `${API_BASE}/jobs/${encodeURIComponent(jobId)}/export/json`,
};
