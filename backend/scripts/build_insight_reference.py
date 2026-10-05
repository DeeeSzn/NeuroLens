"""Build an exploratory reference from previously completed TRIBE audio jobs."""

import argparse
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.database import Job, JobStatus
from app.services.insight_reference import build_reference, source_hash
from app.workers.tasks import _sync_engine


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_ids", nargs="+", help="Fixed, independent completed audio jobs")
    parser.add_argument("--output", type=Path, default=Path("references/audio.json"))
    args = parser.parse_args()
    samples = []
    with Session(_sync_engine) as session:
        for job_id in args.job_ids:
            job = session.scalar(select(Job).where(Job.id == job_id))
            if not job or job.status != JobStatus.COMPLETE or job.media_type != "audio":
                raise ValueError(f"Not a completed audio job: {job_id}")
            if not job.file_path or not job.result_path:
                raise ValueError(f"Missing source/result: {job_id}")
            samples.append((source_hash(job.file_path), json.loads(Path(job.result_path).read_text())))
    reference = build_reference(samples, "audio")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(reference, indent=2) + "\n")
    print(f"Wrote {len(reference['clips'])} independent audio clips to {args.output}")


if __name__ == "__main__":
    main()