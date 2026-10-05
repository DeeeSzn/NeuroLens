"""Run the MPS feature extractors in half precision to shrink their memory.

Why: on a 16 GB Apple-Silicon machine the video extractor (V-JEPA2) alone can
exhaust memory during `Encoding video`; the audio extractor (Wav2Vec-BERT, 2.3 GB
fp32) adds more. `neuralset` loads both in fp32. This module is a *runtime*
monkeypatch applied from our own code (not a site-packages edit) so it is tracked
and survives a re-clone. Only the MPS feature models are affected; the text
extractor (LLaMA) runs on CPU and is deliberately left in fp32.

Two memory problems are addressed:
1. Weight precision  -> load in half precision (weights ~halve).
2. Load transient    -> `from_pretrained` can hold an fp32 copy while producing
   the fp16 one. We release the MPS/CPU allocator cache right after the model is
   moved to the device, before the encode loop starts.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Only these extractors are switched to half precision (matched case-insensitively
# against the HF model id). LLaMA (text) is excluded: it runs on CPU.
_HALF_PRECISION_MODEL_HINTS = ("vjepa2", "w2v-bert", "wav2vec2-bert")

_APPLIED = False


def _dtype_kwarg() -> str:
    """transformers >= 4.56 uses `dtype`; older versions use `torch_dtype`."""
    try:
        import transformers

        major, minor = (int(p) for p in transformers.__version__.split(".")[:2])
        return "dtype" if (major, minor) >= (4, 56) else "torch_dtype"
    except Exception:
        return "torch_dtype"


def _release_mps_cache() -> None:
    """Force pending MPS work to finish and unreferenced buffers to be freed.

    `torch.mps.empty_cache()` alone can no-op if the allocator's freed blocks
    are still pinned behind in-flight (async) GPU work, or if Python hasn't
    collected the tensors referencing them yet. `synchronize()` drains the
    queue first and `gc.collect()` drops any tensors kept alive only by a
    reference cycle, so the cache actually has something to release.
    """
    import gc

    import torch

    try:
        torch.mps.synchronize()
    except Exception:
        pass
    gc.collect()
    try:
        torch.mps.empty_cache()
    except Exception:
        pass


def _wrap_forward_cast(model, empty_cache: bool = True) -> None:
    """Cast floating-point forward inputs to the model dtype, then free the cache.

    Releasing the MPS allocator cache after each forward stops the per-clip
    attention buffer (~3 GB) from being retained across all clips.
    """
    import torch

    if getattr(model, "_tribe_forward_cast", False):
        return
    try:
        dtype = next(model.parameters()).dtype
    except StopIteration:
        return
    original_forward = model.forward

    def forward(*args, **kwargs):
        def cast(value):
            if torch.is_tensor(value) and value.is_floating_point() and value.dtype != dtype:
                return value.to(dtype)
            return value

        try:
            return original_forward(
                *[cast(a) for a in args],
                **{k: cast(v) for k, v in kwargs.items()},
            )
        finally:
            if empty_cache:
                _release_mps_cache()

    model.forward = forward  # type: ignore[assignment]
    model._tribe_forward_cast = True


def _wrap_to_empty_cache(model) -> None:
    """After the model moves to MPS, release the allocator cache (the transient)."""
    if getattr(model, "_tribe_to_cache", False):
        return
    original_to = model.to

    def to(*args, **kwargs):
        result = original_to(*args, **kwargs)
        _release_mps_cache()
        return result

    model.to = to  # type: ignore[assignment]
    model._tribe_to_cache = True


_LOCAL_PATHS_APPLIED = False


def allow_local_model_paths() -> bool:
    """Let neuralset extractors load from a local directory.

    `HuggingFaceMixin.repo_exists` only accepts Hugging Face repo ids (or its
    whitelist), so pointing `model_name` at a local fp16 checkpoint raises
    "The model ... does not exist". Patch it to accept an existing local dir.
    Tracked here rather than editing site-packages. Safe to call repeatedly.
    """
    global _LOCAL_PATHS_APPLIED
    if _LOCAL_PATHS_APPLIED:
        return True
    try:
        import os

        from neuralset.extractors.base import HuggingFaceMixin

        original = HuggingFaceMixin.repo_exists

        def repo_exists(self) -> bool:
            try:
                if os.path.isdir(str(self.model_name)):
                    return True
            except Exception:
                pass
            return original(self)

        HuggingFaceMixin.repo_exists = repo_exists
        _LOCAL_PATHS_APPLIED = True
        logger.info("[precision] local model directories are now accepted")
    except Exception:
        logger.exception("[precision] failed to patch repo_exists")
    return _LOCAL_PATHS_APPLIED


def apply_mps_precision(
    dtype_name: str = "float16", empty_cache_each_call: bool = True
) -> bool:
    """Patch `PreTrainedModel.from_pretrained` for the MPS extractors.

    Returns True if the patch is active. Safe to call more than once.
    """
    global _APPLIED
    if _APPLIED or not dtype_name:
        return _APPLIED

    try:
        import torch
        import transformers

        base = transformers.PreTrainedModel
        original = base.from_pretrained.__func__  # unwrap classmethod
        kwarg = _dtype_kwarg()
        target_dtype = getattr(torch, dtype_name)

        def patched(cls, *args, **kwargs):
            model_id = args[0] if args else kwargs.get("pretrained_model_name_or_path", "")
            if any(h in str(model_id).lower() for h in _HALF_PRECISION_MODEL_HINTS):
                kwargs.setdefault(kwarg, target_dtype)
                # Avoid the fp32->fp16 transient: stream weights straight into
                # half precision instead of materialising the fp32 checkpoint.
                kwargs.setdefault("low_cpu_mem_usage", True)
                try:
                    model = original(cls, *args, **kwargs)
                except Exception:
                    kwargs.pop("low_cpu_mem_usage", None)
                    logger.warning(
                        "[precision] low_cpu_mem_usage failed for %s; retrying without it",
                        model_id,
                    )
                    model = original(cls, *args, **kwargs)
                _wrap_forward_cast(model, empty_cache_each_call)
                _wrap_to_empty_cache(model)
                try:
                    actual = next(model.parameters()).dtype
                except StopIteration:
                    actual = "?"
                logger.info("[precision] %s loaded (%s, low_cpu_mem_usage)", model_id, actual)
                return model
            return original(cls, *args, **kwargs)

        base.from_pretrained = classmethod(patched)
        _APPLIED = True
        logger.info("[precision] MPS extractors will load in %s (kwarg=%s)", dtype_name, kwarg)
    except Exception:
        logger.exception("[precision] failed to apply MPS half-precision patch")
    return _APPLIED
