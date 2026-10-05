"""API router for export/reporting."""

import asyncio
from typing import Tuple

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.database import Job
from app.routers.analysis import _load_job_result
from app.services.export import generate_json_export, generate_text_report
from app.services.insights import evaluate_result
from app.services.insight_rules import RULESET_VERSION

router = APIRouter(prefix="/api", tags=["export"])


async def _get_completed_result(job_id: str, db: AsyncSession) -> Tuple[Job, dict]:
    job, result = await _load_job_result(job_id, db)
    result["insights"], result["insight_reference_version"] = await asyncio.to_thread(
        evaluate_result, result, job.media_type, job.file_path,
    )
    result["insight_ruleset_version"] = RULESET_VERSION
    return job, result


@router.get("/jobs/{job_id}/export/report")
async def export_report(job_id: str, db: AsyncSession = Depends(get_db)):
    """Export analysis as a Markdown text report."""
    job, result = await _get_completed_result(job_id, db)
    report = generate_text_report(result, job_id, job.filename, job.media_type)
    return PlainTextResponse(
        report,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="neurolens-report-{job_id[:8]}.md"'},
    )


@router.get("/jobs/{job_id}/export/json")
async def export_json(job_id: str, db: AsyncSession = Depends(get_db)):
    """Export analysis data as clean JSON (no raw vertices)."""
    job, result = await _get_completed_result(job_id, db)
    export = generate_json_export(result, job_id)
    return JSONResponse(
        export,
        headers={"Content-Disposition": f'attachment; filename="neurolens-data-{job_id[:8]}.json"'},
    )
