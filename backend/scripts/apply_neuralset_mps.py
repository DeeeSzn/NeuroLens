#!/usr/bin/env python3
"""Apply the version-checked neuralset 0.0.2 MPS compatibility patch."""

import argparse
from importlib.metadata import distribution
from pathlib import Path


AUTO_ORIGINAL = '''        if self.device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"'''
AUTO_PATCHED = '''        if self.device == "auto":
            if torch.cuda.is_available():
                self.device = "cuda"
            elif torch.backends.mps.is_available():
                self.device = "mps"
            else:
                self.device = "cpu"'''


def patch_source(source: str, filename: str) -> str:
    literals = {
        "base.py": (
            'tp.Literal["auto", "cpu", "cuda", "accelerate"]',
            'tp.Literal["auto", "cpu", "cuda", "mps", "accelerate"]',
        ),
        "video.py": (
            'tp.Literal["auto", "cpu", "cuda"]',
            'tp.Literal["auto", "cpu", "cuda", "mps"]',
        ),
    }
    if filename not in literals:
        raise ValueError(f"Unexpected extractor: {filename}")
    for original, patched in (literals[filename], (AUTO_ORIGINAL, AUTO_PATCHED)):
        if source.count(original) == 1 and source.count(patched) == 0:
            source = source.replace(original, patched, 1)
        elif source.count(original) != 0 or source.count(patched) != 1:
            raise ValueError(f"Unrecognized neuralset patch context in {filename}")
    return source


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify without modifying files")
    args = parser.parse_args()
    package = distribution("neuralset")
    if package.version != "0.0.2":
        parser.error(f"Expected neuralset 0.0.2, found {package.version}")
    changes: list[tuple[Path, str]] = []
    for filename in ("base.py", "video.py"):
        path = Path(package.locate_file(f"neuralset/extractors/{filename}"))
        source = path.read_text()
        patched = patch_source(source, filename)
        if patched != source:
            changes.append((path, patched))
    if args.check and changes:
        parser.error("MPS patch is missing; run this script without --check")
    for path, patched in changes:
        path.write_text(patched)
        print(f"Patched neuralset/extractors/{path.name}")
    print("neuralset 0.0.2 MPS compatibility verified")


if __name__ == "__main__":
    main()
