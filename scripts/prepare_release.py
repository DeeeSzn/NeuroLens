#!/usr/bin/env python3
"""Check or export a source-only release without touching Git or local data."""

import argparse
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (
    ".gitignore", ".dockerignore", "README.md", "THIRD_PARTY_NOTICES.md", "LICENSE", "NOTICE",
    "package.json", "package-lock.json", "docker-compose.yml", "docker-compose.cuda.yml",
    "backend/Dockerfile", "backend/.dockerignore", "backend/.env.example",
    "backend/requirements.txt", "backend/requirements-runtime.txt",
    "frontend/Dockerfile", "frontend/.dockerignore", "frontend/.eslintrc.json",
    "frontend/package.json", "frontend/package-lock.json", "frontend/next.config.js",
    "frontend/next-env.d.ts", "frontend/tsconfig.json", "frontend/postcss.config.mjs",
    "tribev2/LICENSE", "tribev2/README.md", "tribev2/pyproject.toml",
    "backend/static/.gitkeep", "frontend/public/.gitkeep",
    "scripts/prepare_release.py", "scripts/generate_splayed_meshes.py",
)
SOURCE_TREES = {
    "backend/app": {".py"},
    "backend/tests": {".py"},
    "frontend/src": {".ts", ".tsx", ".js", ".css", ".json", ".svg"},
    "frontend/tests": {".cjs"},
    "tribev2/tribev2": {".py"},
    "scripts/tests": {".py"},
}
BACKEND_SCRIPTS = (
    "apply_neuralset_mps.py", "build_insight_reference.py", "generate_roi_atlas.py",
    "run_inference_local.py", "guard_watchdog.py", "convert_extractors_fp16.py",
    "prepare_assets.py",
)
PRIVATE_DIRS = {
    ".git", ".agents", ".claude", ".copilot", ".vscode", "node_modules", ".next",
    "__pycache__", "venv", ".venv",
}
BACKEND_STATE_DIRS = {"uploads", "results", "cache", "models", "references"}
SECRET_PATTERNS = (
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,}|hf_[A-Za-z0-9]{30,})\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?:https?|redis)://[^\s/:@]+:[^\s/@]+@"),
)


def is_private(path: Path) -> bool:
    if any(part.lower() in PRIVATE_DIRS for part in path.parts):
        return True
    if len(path.parts) >= 2 and path.parts[0].lower() == "backend":
        if path.parts[1].lower() in BACKEND_STATE_DIRS:
            return True
    name = path.name.lower()
    return (
        (name.startswith(".env") and name != ".env.example")
        or (name.endswith(".md") and name.startswith(("activity", "agents", "emotions", "work")))
    )


def release_files(root: Path) -> list[Path]:
    candidates = [Path(name) for name in ROOT_FILES]
    for tree, suffixes in SOURCE_TREES.items():
        candidates.extend(
            path.relative_to(root)
            for path in (root / tree).rglob("*")
            if path.suffix in suffixes and path.is_file()
        )
    candidates.extend(Path("backend/scripts") / name for name in BACKEND_SCRIPTS)
    selected = []
    for relative in sorted(set(candidates)):
        if is_private(relative):
            continue
        absolute = root / relative
        if any(parent.is_symlink() for parent in (absolute, *absolute.parents)):
            raise ValueError(f"Release paths must not be symlinks: {relative}")
        if not absolute.is_file():
            raise ValueError(f"Required release file missing: {relative}")
        selected.append(relative)
    return selected


def check_sources(root: Path, selected: list[Path]) -> None:
    for relative in selected:
        source = (root / relative).read_text(encoding="utf-8")
        if any(pattern.search(source) for pattern in SECRET_PATTERNS):
            raise ValueError(f"Possible credential in {relative}; value suppressed")
        if "/Users/" in source or re.search(r"/home/[^/\s]+/", source):
            # The release checker itself contains these detection patterns.
            if relative != Path("scripts/prepare_release.py"):
                raise ValueError(f"Personal absolute path in {relative}; value suppressed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Create a new source-only directory outside this checkout")
    parser.add_argument("--list", action="store_true", help="Print the complete publication allowlist")
    args = parser.parse_args()
    try:
        selected = release_files(ROOT)
        check_sources(ROOT, selected)
        if args.output is not None:
            output = args.output.expanduser().resolve()
            if output == ROOT or ROOT in output.parents:
                raise ValueError("Release output must be outside the current checkout")
            output.mkdir(parents=True, exist_ok=False)
            for relative in selected:
                destination = output / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, destination)
            print(f"Source-only copy created at {output}")
        print(f"Checked {len(selected)} allowlisted files; no recognized credentials found.")
        print("This is a bounded source check, not dependency, license, or inference certification.")
        if args.list:
            for relative in selected:
                print(relative.as_posix())
    except (OSError, ValueError, UnicodeError) as exc:
        parser.exit(1, f"Release check failed: {exc}\n")


if __name__ == "__main__":
    main()
