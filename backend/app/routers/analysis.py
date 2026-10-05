"""API router for content analysis jobs."""

from __future__ import annotations

import asyncio
import io
import os
import uuid
from contextlib import suppress
from pathlib import Path
import tempfile

import aiofiles
import nibabel as nib
import numpy as np
from typing import List, Tuple
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.database import Job, JobStatus
from app.models.schemas import (
    AnalysisResult,
    BrainTimestepData,
    InsightsResponse,
    JobCreateResponse,
    JobStatusResponse,
    RegionActivation,
    TimelineData,
    TimestepData,
)
from app.services.brain_regions import REGION_ORDER
from app.services.job_control import aclear_cancel, arequest_cancel
from app.services.tribe_wrapper import load_result
from app.workers.tasks import analyze_content

router = APIRouter(prefix="/api", tags=["analysis"])

ALLOWED_EXTENSIONS = settings.allowed_extensions
MAX_SIZE = settings.max_upload_size_mb * 1024 * 1024


def timeline_series(timesteps: List[dict]) -> dict[str, List[float]]:
    """One activation series per region, in REGION_ORDER.

    ``.get`` defaults missing keys to 0.0 so results saved before the named
    regions (tpoj/memory/face_body) existed still load.
    """
    return {
        region: [t["regions"].get(region, 0.0) for t in timesteps]
        for region in REGION_ORDER
    }


def _get_media_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in {".mp4", ".avi", ".mov", ".mkv", ".webm"}:
        return "video"
    if ext in {".mp3", ".wav", ".flac", ".ogg"}:
        return "audio"
    raise ValueError(f"Unsupported file extension: {ext}")


@router.post("/analyze", response_model=JobCreateResponse)
async def create_analysis(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    """Upload a video/audio file and start brain activation analysis."""
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    try:
        media_type = _get_media_type(file.filename)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Stream to disk in chunks, enforcing the size limit as we go so a large
    # upload never has to be buffered in API memory.
    job_id = str(uuid.uuid4())
    safe_filename = f"{job_id}{ext}"
    file_path = settings.upload_dir / safe_filename
    chunk_size = 1024 * 1024
    total = 0
    try:
        async with aiofiles.open(file_path, "wb") as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_SIZE:
                    raise HTTPException(
                        413,
                        f"File too large. Maximum size: {settings.max_upload_size_mb} MB",
                    )
                await f.write(chunk)
    except BaseException:
        # Never leave a partial file behind (oversize, disconnect, cancel, ...)
        with suppress(Exception):
            os.remove(file_path)
        raise

    if total == 0:
        with suppress(Exception):
            os.remove(file_path)
        raise HTTPException(400, "Uploaded file is empty")

    # Create job record
    job = Job(
        id=job_id,
        filename=file.filename,
        file_path=str(file_path),
        media_type=media_type,
        status=JobStatus.PENDING,
    )
    db.add(job)
    await db.commit()

    # Enqueue Celery task. If the broker is unreachable, fail the job record
    # instead of leaving it stuck in "pending" with no task behind it.
    try:
        analyze_content.delay(job_id, str(file_path), media_type)
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error_message = f"Failed to enqueue job: {exc}"
        await db.commit()
        raise HTTPException(503, "Analysis queue unavailable") from exc

    return JobCreateResponse(
        job_id=job_id,
        status="pending",
        message="Analysis started. Poll /api/jobs/{job_id} for status.",
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get the status of an analysis job."""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        progress=job.progress,
        filename=job.filename,
        media_type=job.media_type,
        created_at=job.created_at.isoformat(),
        error_message=job.error_message,
    )


@router.get("/jobs", response_model=List[JobStatusResponse])
async def list_jobs(db: AsyncSession = Depends(get_db)):
    """List all analysis jobs."""
    result = await db.execute(select(Job).order_by(Job.created_at.desc()))
    jobs = result.scalars().all()
    return [
        JobStatusResponse(
            job_id=j.id,
            status=j.status.value,
            progress=j.progress,
            filename=j.filename,
            media_type=j.media_type,
            created_at=j.created_at.isoformat(),
            error_message=j.error_message,
        )
        for j in jobs
    ]


@router.post("/jobs/{job_id}/cancel", response_model=JobCreateResponse)
async def cancel_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Request cancellation of a running job.

    Cooperative: it takes effect at the next inference checkpoint, so a job in
    the middle of the blocking prediction call may still complete that phase.
    """
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != JobStatus.PROCESSING:
        raise HTTPException(409, f"Job is not processing (status: {job.status.value})")
    await arequest_cancel(job_id)
    return JobCreateResponse(
        job_id=job_id,
        status="cancelling",
        message="Cancellation requested; it takes effect at the next checkpoint.",
    )


@router.post("/jobs/{job_id}/retry", response_model=JobCreateResponse)
async def retry_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Re-queue a failed job, reusing the original uploaded file."""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != JobStatus.FAILED:
        raise HTTPException(
            409, f"Only failed jobs can be retried (status: {job.status.value})"
        )
    if not job.file_path or not os.path.exists(job.file_path):
        raise HTTPException(410, "Original upload is no longer available")

    job.status = JobStatus.PENDING
    job.progress = 0.0
    job.error_message = None
    await db.commit()
    await aclear_cancel(job_id)

    try:
        analyze_content.delay(job.id, job.file_path, job.media_type)
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error_message = f"Failed to enqueue job: {exc}"
        await db.commit()
        raise HTTPException(503, "Analysis queue unavailable") from exc

    return JobCreateResponse(job_id=job_id, status="pending", message="Job re-queued.")


async def _load_job_result(job_id: str, db: AsyncSession) -> Tuple[Job, dict]:
    """Helper to load a completed job's result."""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != JobStatus.COMPLETE:
        raise HTTPException(400, f"Job is not complete (status: {job.status.value})")
    if not job.result_path or not os.path.exists(job.result_path):
        raise HTTPException(500, "Result file missing")
    from app.services.insight_reference import with_current_regions

    result = await asyncio.to_thread(load_result, job.result_path)
    return job, await asyncio.to_thread(with_current_regions, result)


@router.get("/jobs/{job_id}/result", response_model=AnalysisResult)
async def get_job_result(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get the full analysis result for a completed job."""
    job, result = await _load_job_result(job_id, db)
    return AnalysisResult(
        job_id=job.id,
        filename=job.filename,
        media_type=job.media_type,
        duration_sec=result["duration_sec"],
        n_timesteps=result["n_timesteps"],
        tr_seconds=result["tr_seconds"],
        timesteps=[
            TimestepData(
                time_sec=t["time_sec"],
                regions=RegionActivation(**t["regions"]),
                top_rois=t["top_rois"],
                words=t["words"],
            )
            for t in result["timesteps"]
        ],
    )


@router.get("/jobs/{job_id}/brain/{timestep}", response_model=BrainTimestepData)
async def get_brain_timestep(
    job_id: str, timestep: int, db: AsyncSession = Depends(get_db)
):
    """Get vertex-level brain data for a single timestep (for 3D visualization)."""
    job, result = await _load_job_result(job_id, db)
    if timestep < 0 or timestep >= result["n_timesteps"]:
        raise HTTPException(400, f"Invalid timestep. Range: 0–{result['n_timesteps'] - 1}")
    ts = result["timesteps"][timestep]
    vertices = result["raw_vertices"][timestep] if "raw_vertices" in result else []
    return BrainTimestepData(
        timestep=timestep,
        time_sec=ts["time_sec"],
        vertices=vertices,
        regions=RegionActivation(**ts["regions"]),
    )


@router.get("/jobs/{job_id}/timeline", response_model=TimelineData)
async def get_timeline(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get lightweight timeline data (region activations over time)."""
    job, result = await _load_job_result(job_id, db)
    timesteps = result["timesteps"]
    return TimelineData(
        job_id=job.id,
        tr_seconds=result["tr_seconds"],
        times=[t["time_sec"] for t in timesteps],
        **timeline_series(timesteps),
    )


@router.get("/jobs/{job_id}/insights", response_model=InsightsResponse)
async def get_insights(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get benchmarked exploratory findings for a completed analysis."""
    job, result = await _load_job_result(job_id, db)
    from app.services.insights import evaluate_result

    insights, reference_version = await asyncio.to_thread(evaluate_result, result, job.media_type, job.file_path)
    return InsightsResponse(
        job_id=job.id, insights=insights,
        reference_status="exploratory" if reference_version else "unavailable",
        reference_version=reference_version,
    )


# ---------------------------------------------------------------------------
# GIFTI overlay endpoint — returns activation values as a GIFTI func file
# so NiiVue can use it as a mesh overlay layer.
# ---------------------------------------------------------------------------

_MESH_DIR = Path(__file__).parent.parent.parent / "static" / "meshes"
_GIFTI_MEDIA_TYPE = "application/gii+xml"


@router.get("/jobs/{job_id}/overlay/{hemi}/{timestep}")
async def get_gifti_overlay(
    job_id: str,
    hemi: str,
    timestep: int,
    db: AsyncSession = Depends(get_db),
):
    """Return a GIFTI functional overlay for NiiVue.

    hemi: 'lh' (left, vertices 0-10241) or 'rh' (right, vertices 10242-20483)
    timestep: index into raw_vertices array
    """
    if hemi not in ("lh", "rh"):
        raise HTTPException(400, "hemi must be 'lh' or 'rh'")

    job, result = await _load_job_result(job_id, db)
    n_ts = result["n_timesteps"]
    if timestep < 0 or timestep >= n_ts:
        raise HTTPException(400, f"timestep out of range 0–{n_ts - 1}")

    raw = np.array(result["raw_vertices"][timestep], dtype=np.float32)
    # Split hemispheres: LH = first 10242, RH = last 10242
    if hemi == "lh":
        arr = raw[:10242]
    else:
        arr = raw[10242:]

    # Build a minimal GIFTI func file (one scalar darray per vertex)
    darray = nib.gifti.GiftiDataArray(
        data=arr,
        intent=nib.nifti1.intent_codes["NIFTI_INTENT_NONE"],
        datatype="NIFTI_TYPE_FLOAT32",
    )
    gifti_img = nib.gifti.GiftiImage(darrays=[darray])

    # nibabel requires a real file path to serialize GIFTI
    with tempfile.NamedTemporaryFile(suffix=".func.gii", delete=False) as f:
        tmp_path = f.name
    try:
        nib.save(gifti_img, tmp_path)
        with open(tmp_path, "rb") as f:
            data = f.read()
    finally:
        os.unlink(tmp_path)

    return Response(content=data, media_type=_GIFTI_MEDIA_TYPE)


# ---------------------------------------------------------------------------
# All vertex data in one shot — used for live brain playback synced to video
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}/all-vertices")
async def get_all_vertices(job_id: str, db: AsyncSession = Depends(get_db)):
    """Return normalised per-vertex activations for every timestep.

    Response:
        {
            n_timesteps: int,
            n_vertices: int,          # 20484 for fsaverage5
            vertices: number[][],     # [timestep][vertex] – values in [0, 1]
        }
    """
    job, result = await _load_job_result(job_id, db)
    # raw_vertices are normalized exactly once at inference time (see
    # tribe_wrapper._robust_normalize); do not re-normalize here.
    raw = np.array(result["raw_vertices"], dtype=np.float32)  # (T, V) in [0, 1]
    return {
        "n_timesteps": int(raw.shape[0]),
        "n_vertices": int(raw.shape[1]),
        "vertices": raw.tolist(),
    }


# ---------------------------------------------------------------------------
# 4-D GIFTI overlay — all timesteps in a single file (one darray per frame)
# ---------------------------------------------------------------------------

_LH_VERTS = 10242  # fsaverage5 left hemisphere vertex count


@router.get("/jobs/{job_id}/overlay-4d/{hemi}")
async def get_gifti_overlay_4d(
    job_id: str,
    hemi: str,
    db: AsyncSession = Depends(get_db),
):
    """Return a multi-frame GIFTI overlay (one DataArray per timestep).

    NiiVue loads this as a single layer with nFrame4D == n_timesteps,
    then frame switching is done via setMeshLayerProperty('frame4D', idx).
    """
    if hemi not in ("lh", "rh"):
        raise HTTPException(400, "hemi must be 'lh' or 'rh'")

    job, result = await _load_job_result(job_id, db)
    # Already normalized once at inference time; serve as-is. (Previously this
    # re-normalized on top of the stored values, which was environment-dependent.)
    normed = np.array(result["raw_vertices"], dtype=np.float32)  # (T, V_total) in [0, 1]

    # Split per hemisphere
    if hemi == "lh":
        hemi_data = normed[:, :_LH_VERTS]
    else:
        hemi_data = normed[:, _LH_VERTS:]

    # Build multi-frame GIFTI: one darray per timestep
    darrays = []
    for t in range(hemi_data.shape[0]):
        da = nib.gifti.GiftiDataArray(
            data=hemi_data[t].astype(np.float32),
            intent=nib.nifti1.intent_codes["NIFTI_INTENT_NONE"],
            datatype="NIFTI_TYPE_FLOAT32",
        )
        darrays.append(da)
    gifti_img = nib.gifti.GiftiImage(darrays=darrays)

    with tempfile.NamedTemporaryFile(suffix=".func.gii", delete=False) as f:
        tmp_path = f.name
    try:
        nib.save(gifti_img, tmp_path)
        with open(tmp_path, "rb") as f:
            data = f.read()
    finally:
        os.unlink(tmp_path)

    return Response(content=data, media_type=_GIFTI_MEDIA_TYPE)


# ---------------------------------------------------------------------------
# Serve the uploaded media file (video/audio) for in-browser playback
# ---------------------------------------------------------------------------

_MEDIA_TYPES = {
    ".mp4": "video/mp4",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
}


@router.get("/jobs/{job_id}/video")
async def get_job_media(job_id: str, db: AsyncSession = Depends(get_db)):
    """Stream the original uploaded media file for in-browser playback."""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if not job.file_path or not os.path.exists(job.file_path):
        raise HTTPException(404, "Media file not found")
    ext = Path(job.file_path).suffix.lower()
    media_type = _MEDIA_TYPES.get(ext, "application/octet-stream")
    return FileResponse(job.file_path, media_type=media_type, filename=job.filename)
