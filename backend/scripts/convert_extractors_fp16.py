#!/usr/bin/env python
"""Convert the TRIBE feature extractors to local fp16 checkpoints.

Why: `from_pretrained(dtype=float16)` on the fp32 Hub checkpoints momentarily
materialises both the fp32 and fp16 copies (a ~5 GB transient on V-JEPA2) which
macOS does not hand back before inference starts. Storing fp16 weights on disk
means later loads never build an fp32 copy, so the transient disappears.

Output-preserving: fp16 weights are numerically the same as loading with
`dtype=float16`; nothing about the architecture, layers or inputs changes.

Usage (from backend/):
    ./venv/bin/python scripts/convert_extractors_fp16.py
"""

import os
import shutil
import time

import torch
from huggingface_hub import snapshot_download
from transformers import AutoModel

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ROOT = os.path.join(BACKEND, "models")

JOBS = [
    ("facebook/vjepa2-vitg-fpc64-256", "vjepa2-vitg-fpc64-256-fp16"),
    ("facebook/w2v-bert-2.0", "w2v-bert-2.0-fp16"),
]


def convert(model_id: str, out_name: str) -> None:
    out = os.path.join(OUT_ROOT, out_name)
    os.makedirs(out, exist_ok=True)
    t0 = time.time()

    # 1. Copy the small config/processor json (and tokenizer text) from the snapshot
    #    so the local dir is a complete, loadable model repository.
    src = snapshot_download(model_id, allow_patterns=["*.json", "*.txt"])
    for name in os.listdir(src):
        if name.endswith((".json", ".txt")):
            shutil.copy(os.path.join(src, name), os.path.join(out, name))

    # 2. Save the weights in fp16.
    model = AutoModel.from_pretrained(model_id, dtype=torch.float16, low_cpu_mem_usage=True)
    model.save_pretrained(out, safe_serialization=True)
    size = sum(
        os.path.getsize(os.path.join(out, f))
        for f in os.listdir(out)
        if f.endswith(".safetensors")
    )
    print(f"{model_id} -> {out}  ({size/1e9:.2f} GB, {time.time()-t0:.0f}s)", flush=True)


if __name__ == "__main__":
    os.makedirs(OUT_ROOT, exist_ok=True)
    for mid, name in JOBS:
        convert(mid, name)
    print("CONVERT_DONE", flush=True)
