"""Reference-relative findings derived from predicted regional responses."""

from pathlib import Path

from app.services.insight_rules import evaluate
from app.services.insight_reference import load_reference, source_hash


def generate_insights(
    timesteps: list[dict],
    tr_seconds: float,
    media_type: str = "audio",
    reference: dict | None = None,
    source_fingerprint: str | None = None,
) -> list[dict]:
    return evaluate(timesteps, tr_seconds, media_type, reference, source_fingerprint)


def evaluate_result(result: dict, media_type: str, file_path: str | None) -> tuple[list[dict], str | None]:
    reference = load_reference(media_type)
    if reference is None or not file_path or not Path(file_path).exists():
        return [], None
    findings = generate_insights(
        result["timesteps"], result["tr_seconds"], media_type,
        reference, source_hash(file_path),
    )
    return findings, reference["version"]