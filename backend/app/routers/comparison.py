"""API router for A/B content comparison."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.database import Job, JobStatus
from app.models.schemas import ComparisonResult
from app.services.comparison import compare_analyses
from app.services.insight_reference import with_current_regions
from app.services.tribe_wrapper import load_result

router = APIRouter(prefix="/api", tags=["comparison"])


@router.get("/compare/{job_a_id}/{job_b_id}", response_model=ComparisonResult)
async def compare_jobs(
    job_a_id: str,
    job_b_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Compare brain activation between two completed analyses."""
    for jid in (job_a_id, job_b_id):
        job = await db.get(Job, jid)
        if not job:
            raise HTTPException(404, f"Job {jid} not found")
        if job.status != JobStatus.COMPLETE:
            raise HTTPException(400, f"Job {jid} is not complete")
        if not job.result_path:
            raise HTTPException(500, f"Job {jid} has no result file")

    job_a = await db.get(Job, job_a_id)
    job_b = await db.get(Job, job_b_id)
    result_a = await asyncio.to_thread(lambda: with_current_regions(load_result(job_a.result_path)))
    result_b = await asyncio.to_thread(lambda: with_current_regions(load_result(job_b.result_path)))

    comp = compare_analyses(result_a, result_b)

    return ComparisonResult(
        job_a_id=job_a_id,
        job_b_id=job_b_id,
        summary=comp["summary"],
        deltas=comp["deltas"],
        insights=comp["insights"],
    )
