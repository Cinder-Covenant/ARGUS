"""Shared-feature tiled Hecate prediction for paired 2D and 3D outputs.

This keeps the pinned Hecate provider and checkpoint untouched.  It computes the
existing 2D attention head and 3D head from one ``features_logits`` call per tile,
then blends both outputs with the same Hann weights.  It is an implementation
helper, not a provider qualification or authorization to run on target material.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np


def shared_logits(model, image, valid):
    """Return the pinned Hecate 2D and 3D logits using one shared feature pass.

    ``image`` is normalized B1ZYX float input; ``valid`` is the corresponding
    boolean support mask.  The projections mirror ``Hecate.forward`` and
    ``Hecate.forward_3d`` in the pinned provider, including 2.4 um depth margins.
    """
    import torch
    import torch.nn.functional as F

    if image.ndim != 5 or image.shape[1] != 1:
        raise ValueError("image must have B1ZYX shape")
    if valid is not None and tuple(valid.shape) != tuple(image.shape):
        raise ValueError("valid support must match image shape")

    features, logits = model.features_logits(image)
    depth = image.shape[2]
    margin = int(model.margin)
    inner_depth = depth - 2 * margin
    if inner_depth <= 0:
        raise ValueError("model margin leaves no evaluated depth")

    scores = model.canonical.decoder.depth_collapse.attn_conv(features).float()
    half = scores.shape[2] // 2
    z = (torch.arange(scores.shape[2], device=scores.device, dtype=torch.float32) - half) / half
    scores = scores + model.depth_coordinate_scale * z.view(1, 1, -1, 1, 1)
    if valid is None:
        support = torch.ones_like(logits, dtype=torch.bool)
    else:
        support = F.max_pool3d(
            valid[:, :, margin:depth - margin].float(),
            (1, model.xy_stride, model.xy_stride),
        ).bool()
    weights = scores.masked_fill(~support, -1e4).softmax(2) * support
    weights = weights / weights.sum(2, keepdim=True).clamp_min(1e-8)
    probability_2d = F.interpolate(
        (weights * logits).sum(2).sigmoid(), size=image.shape[-2:],
        mode="bilinear", align_corners=False,
    )
    eps = torch.finfo(torch.float32).eps
    logits_2d = torch.logit(probability_2d.clamp(eps, 1 - eps))

    logits_3d = F.interpolate(
        logits, size=(inner_depth, *image.shape[-2:]),
        mode="trilinear", align_corners=False,
    )
    if margin:
        logits_3d = F.pad(logits_3d, (0, 0, 0, 0, margin, margin), value=-20.0)
    return logits_2d.float(), logits_3d.float()


def _axis_starts(length: int, patch: int, stride: int) -> list[int]:
    # Kept byte-for-byte equivalent in behavior to the pinned helper.
    return list(range(0, max(0, length - patch), stride)) + [max(0, length - patch)]


def predict_both(
    model,
    volume,
    output_2d: np.ndarray,
    output_3d: np.ndarray,
    *,
    reverse: bool = False,
    stride: int | None = None,
    batch_size: int = 1,
    precision: str = "fp32",
    before_batch: Callable[[], None] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Stream one input into both uint8 outputs, sharing Hecate's feature pass.

    Accumulators are disk-backed temporary arrays.  Inputs and outputs follow
    the pinned provider's ZYX/HW layouts, central-depth selection, reverse order,
    Hann overlap weighting, and uint8 probability conversion.
    """
    import tempfile
    from contextlib import ExitStack

    import torch

    if len(volume.shape) != 3 or np.dtype(volume.dtype) != np.dtype("uint8"):
        raise ValueError("volume must be an unnormalized uint8 Z,Y,X array")
    depth, height, width = map(int, volume.shape)
    model_depth, patch, _ = model.patch_size
    stride = patch // 2 if stride is None else int(stride)
    batch_size = int(batch_size)
    if depth < model_depth or not 0 < stride <= patch or batch_size < 1:
        raise ValueError("insufficient depth, invalid stride, or invalid batch size")
    if tuple(output_2d.shape) != (height, width) or output_2d.dtype != np.uint8:
        raise ValueError("output_2d must be uint8 with shape (Y,X)")
    if tuple(output_3d.shape) != (depth, height, width) or output_3d.dtype != np.uint8:
        raise ValueError("output_3d must be uint8 with shape (Z,Y,X)")

    device = next(model.parameters()).device
    if precision not in ("fp32", "bf16") or (precision == "bf16" and device.type != "cuda"):
        raise ValueError("bf16 requires CUDA; otherwise use fp32")

    z0 = depth // 2 - model_depth // 2
    selected_z0 = depth - z0 - model_depth if reverse else z0
    zs = slice(selected_z0, selected_z0 + model_depth)
    window_t = torch.hann_window(patch, periodic=False)
    window_t = window_t[:, None] * window_t[None, :]
    window_t = (window_t / window_t.max().clamp_min(torch.finfo(torch.float32).eps)).clamp_min(0.001)
    window_np = window_t.numpy()
    window_t = window_t.to(device)
    origins = [(y, x) for y in _axis_starts(height, patch, stride)
               for x in _axis_starts(width, patch, stride)]
    output_3d[:] = 0
    blank_tiles = 0

    with tempfile.TemporaryDirectory(prefix="argus-hecate-shared-") as tmp, ExitStack() as stack:
        def accumulator(name: str, shape: tuple[int, ...]):
            array = np.memmap(f"{tmp}/{name}", mode="w+", dtype="float32", shape=shape)
            stack.callback(array._mmap.close)
            return array

        numerator_2d = accumulator("sum2d", (height, width))
        numerator_3d = accumulator("sum3d", (model_depth, height, width))
        denominator = accumulator("weight", (height, width))
        numerator_2d[:] = 0
        numerator_3d[:] = 0
        denominator[:] = 0

        for start in range(0, len(origins), batch_size):
            if before_batch is not None:
                before_batch()
            active, patches = [], []
            for y, x in origins[start:start + batch_size]:
                ph, pw = min(patch, height - y), min(patch, width - x)
                denominator[y:y + ph, x:x + pw] += window_np[:ph, :pw]
                raw = np.asarray(volume[zs, y:y + ph, x:x + pw])
                if reverse:
                    raw = raw[::-1]
                if not raw.any():
                    blank_tiles += 1
                    continue
                padded = np.zeros((model_depth, patch, patch), dtype=np.uint8)
                padded[:, :ph, :pw] = raw
                patches.append(padded)
                active.append((y, x, ph, pw))

            if patches:
                raw_batch = np.stack(patches)
                support = torch.from_numpy(raw_batch).to(device).any(1)
                normalized = raw_batch.astype(np.float32)
                normalized /= model.divisor
                image = torch.from_numpy(normalized[:, None]).to(device)
                valid = support[:, None, None].expand(-1, 1, model_depth, -1, -1)
                with torch.inference_mode(), torch.autocast(
                    device_type=device.type, dtype=torch.bfloat16, enabled=precision == "bf16"
                ):
                    logits_2d, logits_3d = shared_logits(model, image, valid)
                    probability_2d = logits_2d.float().sigmoid()[:, 0]
                    probability_3d = logits_3d.float().sigmoid()[:, 0]
                    weighted_2d = (probability_2d * support * window_t).cpu().numpy()
                    weighted_3d = (probability_3d * support[:, None] * window_t).cpu().numpy()
                for pred2, pred3, (y, x, ph, pw) in zip(weighted_2d, weighted_3d, active):
                    numerator_2d[y:y + ph, x:x + pw] += pred2[:ph, :pw]
                    numerator_3d[:, y:y + ph, x:x + pw] += pred3[:, :ph, :pw]
            if progress is not None:
                progress(min(start + batch_size, len(origins)), len(origins))

        if model.margin:
            numerator_3d[:model.margin] = 0
            numerator_3d[-model.margin:] = 0
        for y in range(0, height, 128):
            for x in range(0, width, 256):
                y1, x1 = min(height, y + 128), min(width, x + 256)
                den = denominator[y:y1, x:x1]
                if not np.isfinite(den).all() or np.any(den <= 0):
                    raise FloatingPointError("non-finite or uncovered output pixels")
                prob2 = numerator_2d[y:y1, x:x1] / den
                prob3 = numerator_3d[:, y:y1, x:x1] / den[None]
                if not np.isfinite(prob2).all() or not np.isfinite(prob3).all():
                    raise FloatingPointError("non-finite inference output")
                values2 = np.rint(prob2.clip(0, 1) * 255).astype(np.uint8)
                values3 = np.rint(prob3.clip(0, 1) * 255).astype(np.uint8)
                output_2d[y:y1, x:x1] = values2
                output_3d[zs, y:y1, x:x1] = values3[::-1] if reverse else values3

        numerator_2d.flush()
        numerator_3d.flush()
        denominator.flush()
        del numerator_2d, numerator_3d, denominator

    return {"tile_count": len(origins), "blank_tiles_skipped": blank_tiles,
            "evaluated_z_interval": [selected_z0 + model.margin,
                                     selected_z0 + model_depth - model.margin],
            "reverse": bool(reverse), "stride": stride, "precision": precision}
