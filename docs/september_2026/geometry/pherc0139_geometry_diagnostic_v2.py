"""Version 2 replay of the registered PHerc0139 evaluation-mask diagnostic.

The original local method was frozen in METHOD_FROZEN_BEFORE_RUN.json before
analysis. This successor keeps scientific input hashes separate from run
receipt provenance, pins the scroll/crop/exposure contract, and refuses changed
scientific inputs between preflight and analysis. It never runs inference or
downloads data. The v1 source and receipts remain unchanged for history.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

os.environ["OMP_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"

import numcodecs
import numpy as np
from PIL import Image
from scipy import ndimage
from sklearn.metrics import roc_auc_score


HERE = Path(__file__).resolve().parent
METHOD = HERE / "METHOD_FROZEN_BEFORE_RUN.json"
REFERENCE_INPUTS = HERE / "REFERENCE_INPUTS_V2.json"
EXPECTED_METHOD_SHA256 = "90887d0836807be48c46309c25ced1692d7439418bb0d2aba6cccca58b33f040"
EXPECTED_REFERENCE_SHA256 = "5cef2a7f1a308e44f602dd6204aae47981ea448255ca2be78112ee412638e7e1"
ROOT: Path
PREFLIGHT: Path
RESULT: Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, document: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(document, indent=2, sort_keys=True) + "\n")


def auc_uint8(scores: np.ndarray, truth: np.ndarray) -> float:
    pos = np.bincount(scores[truth], minlength=256).astype(np.float64)
    neg = np.bincount(scores[~truth], minlength=256).astype(np.float64)
    if not pos.sum() or not neg.sum():
        raise ValueError("AUC requires both classes")
    return float(np.sum(pos * (np.cumsum(neg) - 0.5 * neg)) / (pos.sum() * neg.sum()))


def auc_hist(pos: np.ndarray, neg: np.ndarray) -> float | None:
    if not pos.sum() or not neg.sum():
        return None
    return float(np.sum(pos * (np.cumsum(neg) - 0.5 * neg)) / (pos.sum() * neg.sum()))


def ap_uint8(scores: np.ndarray, truth: np.ndarray) -> float:
    pos = np.bincount(scores[truth], minlength=256).astype(np.float64)
    neg = np.bincount(scores[~truth], minlength=256).astype(np.float64)
    tp, fp = np.cumsum(pos[::-1]), np.cumsum(neg[::-1])
    precision = np.divide(tp, tp + fp, out=np.zeros_like(tp), where=(tp + fp) > 0)
    return float(np.sum((pos[::-1] / pos.sum()) * precision))


def stage(receipt: dict, name: str) -> dict:
    matches = [item for item in receipt.get("stages", []) if item.get("stage") == name]
    if len(matches) != 1 or matches[0].get("state") != "RAN":
        raise ValueError(f"receipt must contain exactly one completed {name!r} stage")
    return matches[0]


def receipt_context(receipt: dict) -> dict:
    """Return only stable acquisition/science identity; omit volatile paths/times."""
    identify = stage(receipt, "identify").get("detail", {})
    prepare = stage(receipt, "prepare").get("detail", {})
    attrs = prepare.get("attrs", {})
    score = stage(receipt, "score").get("detail", {})
    metric = score.get("metric", {})
    result = receipt.get("result_class", {})
    contract = stage(receipt, "contract").get("detail", {})
    checks = contract.get("checks", [])
    pitch_checks = [item for item in checks
                    if item.get("check") == "source pitch of the crop's level (um)"]
    model = stage(receipt, "acquire_model").get("detail", {})
    crop = prepare.get("crop", {})
    context = {
        "schema": receipt.get("schema"),
        "outcome": receipt.get("outcome"),
        "target": receipt.get("target"),
        "identity": {key: identify.get(key) for key in
                     ("scroll", "public_name", "volume_id", "scan_id", "pixel_size_um", "energy_kev")},
        "crop": {
            "shape": crop.get("shape"),
            "source_shape_zyx": attrs.get("source_shape_zyx"),
            "source_level": attrs.get("source_level"),
            "source_z_slice": attrs.get("source_z_slice"),
            "z_pool": attrs.get("z_pool"),
            "format": attrs.get("format"),
            "source_pitch_um": pitch_checks[0].get("got") if len(pitch_checks) == 1 else None,
        },
        "score": {
            "rule_id": metric.get("rule_id"), "label_plane": score.get("label_plane"),
            "scored_pixels": score.get("scored_pixels"),
            "validation_pixels": metric.get("n"), "positive_pixels": metric.get("n_positive"),
            "auc": metric.get("auc"), "ap": metric.get("ap"),
            "validation_pixels_also_in_supervision_mask": score.get("validation_pixels_also_in_supervision_mask"),
        },
        "exposure": {
            "target_class": result.get("target_class"),
            "exposure_basis": result.get("exposure_basis"),
            "detector_cross_scroll_qualified": result.get("detector_cross_scroll_qualified"),
            "presentation": result.get("presentation"),
            "may_claim_discovery": result.get("may_claim_discovery"),
            "may_claim_ink_found": result.get("may_claim_ink_found"),
            "case_in_training_datasets": contract.get("exposure_evidence", {}).get("case_in_training_datasets"),
        },
        "checkpoint_sha256": model.get("sha256"),
    }
    return context


def receipt_provenance(receipt: dict, receipt_sha256: str) -> dict:
    """Record receipt provenance without using it as scientific input identity."""
    environment = receipt.get("environment", {})
    return {
        "receipt_sha256": receipt_sha256,
        "run_id": receipt.get("run_id"),
        "started_utc": receipt.get("started_utc"),
        "finished_utc": receipt.get("finished_utc"),
        "source_commit": environment.get("source_commit"),
        "driver_python": environment.get("driver_python"),
        "platform": environment.get("platform"),
        "private_path_fields_omitted": True,
    }


def decode_inputs() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray,
                              dict[str, str], dict, str]:
    hashes: dict[str, str] = {}

    def read(path: Path) -> bytes:
        body = path.read_bytes()
        hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(body).hexdigest()
        return body

    def plane(name: str) -> np.ndarray:
        folder = ROOT / "labels" / name
        meta = json.loads(read(folder / ".zarray"))
        cz, cy, cx = meta["chunks"]
        if meta["order"] != "C" or np.dtype(meta["dtype"]) != np.dtype("uint8") or meta.get("filters"):
            raise ValueError(f"unexpected {name} mask storage")
        codec = numcodecs.get_codec(meta["compressor"])
        y0, y1, x0, x1, z = 4736, 5632, 1664, 2304, 10
        out = np.full((y1 - y0, x1 - x0), meta.get("fill_value") or 0, dtype=np.uint8)
        for yi in range(y0 // cy, (y1 - 1) // cy + 1):
            for xi in range(x0 // cx, (x1 - 1) // cx + 1):
                path = folder / f"{z // cz}.{yi}.{xi}"
                if not path.is_file():
                    raise FileNotFoundError(f"missing required label chunk {path}")
                tile = np.frombuffer(codec.decode(read(path)), dtype=np.uint8).reshape(cz, cy, cx)[z % cz]
                sy, sx = yi * cy, xi * cx
                ya, yb, xa, xb = max(y0, sy), min(y1, sy + cy), max(x0, sx), min(x1, sx + cx)
                out[ya-y0:yb-y0, xa-x0:xb-x0] = tile[ya-sy:yb-sy, xa-sx:xb-sx]
        return out

    ink, supervision, validation = [plane(n) for n in ("ink", "supervision", "validation")]
    prediction_bytes = read(ROOT / "prediction.tif")
    if hashlib.sha256(prediction_bytes).hexdigest() != "4e24125200a8ef8981566eb1f43568fc4b1a001ce30dd696c3c85b366e35288c":
        raise ValueError("retained prediction identity changed")
    prediction = np.asarray(Image.open(ROOT / "prediction.tif"))
    if prediction.shape != ink.shape or prediction.dtype != np.uint8:
        raise ValueError("prediction/label registration or dtype changed")
    receipt_path = ROOT / "PIPELINE_RUN_RECEIPT.json"
    receipt_bytes = receipt_path.read_bytes()
    receipt_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
    receipt = json.loads(receipt_bytes)
    reference = json.loads(REFERENCE_INPUTS.read_text(encoding="utf-8"))
    context = receipt_context(receipt)
    if context != reference["receipt_contract"]:
        raise ValueError("receipt scroll, crop, exposure, checkpoint, or score contract changed")
    metric = stage(receipt, "score")["detail"]["metric"]
    valid = validation > 0
    truth = ink[valid] > 0
    scores = prediction[valid]
    if int(valid.sum()) != 90367 or int(truth.sum()) != 22765:
        raise ValueError("validation population changed")
    if np.any(valid & (supervision > 0)):
        raise ValueError("validation overlaps supervision")
    if abs(auc_uint8(scores, truth) - metric["auc"]) > 1e-12:
        raise ValueError("original AUC could not be reproduced")
    return prediction, ink, supervision, validation, hashes, receipt, receipt_sha256


def run() -> None:
    global ROOT, PREFLIGHT, RESULT
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "analyze"))
    parser.add_argument("--root", required=True, type=Path, help="retained PHerc0139 control root")
    parser.add_argument("--output-dir", required=True, type=Path, help="new receipt directory")
    args = parser.parse_args()
    phase = args.phase
    ROOT = args.root.resolve()
    output_dir = args.output_dir.resolve()
    method_sha = sha(METHOD)
    reference_sha = sha(REFERENCE_INPUTS)
    if method_sha != EXPECTED_METHOD_SHA256:
        raise ValueError("frozen method file does not match the published identity")
    if reference_sha != EXPECTED_REFERENCE_SHA256:
        raise ValueError("registered input reference changed")
    if phase == "preflight":
        output_dir.mkdir(parents=True, exist_ok=False)
    elif not output_dir.is_dir():
        raise FileNotFoundError("preflight output directory is absent")
    PREFLIGHT = output_dir / "PREFLIGHT.json"
    RESULT = output_dir / "RESULT.json"
    method = json.loads(METHOD.read_text(encoding="utf-8"))
    # input_root in the frozen method is historical provenance. Scientific
    # identity is the pinned prediction/label bytes plus the receipt contract;
    # volatile receipt paths and timestamps are recorded separately.
    prediction, ink, supervision, validation, hashes, receipt, receipt_sha = decode_inputs()
    reference = json.loads(REFERENCE_INPUTS.read_text(encoding="utf-8"))
    if hashes != reference["scientific_input_sha256"]:
        raise ValueError("retained prediction or label chunk hashes differ from the registered scientific input set")
    source_sha = sha(Path(__file__))
    context = receipt_context(receipt)
    provenance = receipt_provenance(receipt, receipt_sha)
    if phase == "preflight":
        document = {
            "state": "FROZEN_INPUT_IDENTITY_PASSED", "recorded_utc": datetime.now(timezone.utc).isoformat(),
            "source_sha256": source_sha, "method_sha256": method_sha,
            "reference_sha256": reference_sha,
            "scientific_input_sha256": hashes, "receipt_contract": context,
            "receipt_provenance": provenance, "prediction_shape": list(prediction.shape),
            "validation_pixels": int((validation > 0).sum()),
            "positive_pixels": int(np.sum((validation > 0) & (ink > 0))),
            "validation_supervision_overlap": int(np.sum((validation > 0) & (supervision > 0))),
        }
        write_new(PREFLIGHT, document)
        print(json.dumps({k: v for k, v in document.items() if k != "scientific_input_sha256"}))
        return
    preflight = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
    if (preflight["source_sha256"] != source_sha or preflight["method_sha256"] != method_sha or
            preflight["reference_sha256"] != reference_sha or
            preflight["scientific_input_sha256"] != hashes or preflight["receipt_contract"] != context):
        raise ValueError("source, method, reference, scientific input, or receipt contract changed since preflight")
    valid = validation > 0
    truth = ink[valid] > 0
    scores = prediction[valid]
    model_auc = auc_uint8(scores, truth)
    distance = ndimage.distance_transform_edt(valid)
    d = distance[valid]
    geometry_auc = float(roc_auc_score(truth, d))
    strata = []
    weighted_auc_sum = 0.0
    pairs_total = 0
    included_pixels = 0
    for low, high in method["boundary_distance_strata_pixels"]:
        chosen = (d >= low) if high is None else ((d >= low) & (d < high))
        y = truth[chosen]
        n, pos, neg = int(chosen.sum()), int(y.sum()), int((~y).sum())
        row = {"distance_lo": low, "distance_hi_exclusive": high,
               "pixels": n, "positives": pos, "negatives": neg}
        if n < 2000 or pos == 0 or neg == 0:
            row["auc"] = None
            row["refusal"] = "below 2000 pixels or single class"
        else:
            row["auc"] = auc_uint8(scores[chosen], y)
            row["geometry_only_auc"] = float(roc_auc_score(y, d[chosen]))
            pairs = pos * neg
            weighted_auc_sum += row["auc"] * pairs
            pairs_total += pairs
            included_pixels += n
        strata.append(row)
    within_strata_auc = weighted_auc_sum / pairs_total if pairs_total else None

    yy, xx = np.where(valid)
    block_id = (yy // 64) * 1000 + (xx // 64)
    occupied = np.unique(block_id)
    block_indices = [np.flatnonzero(block_id == block) for block in occupied]
    block_pos = np.stack([np.bincount(scores[index][truth[index]], minlength=256) for index in block_indices])
    block_neg = np.stack([np.bincount(scores[index][~truth[index]], minlength=256) for index in block_indices])
    rng = np.random.default_rng(20260930)
    null_aucs = []
    for _ in range(199):
        shuffled = truth.copy()
        for index in block_indices:
            shuffled[index] = rng.permutation(shuffled[index])
        null_aucs.append(auc_uint8(scores, shuffled))
    bootstrap = []
    degenerate = 0
    for _ in range(512):
        draw = rng.integers(0, len(block_indices), size=len(block_indices))
        value = auc_hist(block_pos[draw].sum(axis=0), block_neg[draw].sum(axis=0))
        if value is None:
            degenerate += 1
        else:
            bootstrap.append(value)
    if not bootstrap:
        raise ValueError("all block-bootstrap replicates were degenerate")
    document = {
        "state": "KNOWN_DOMAIN_DIAGNOSTIC_COMPLETE", "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": source_sha, "method_sha256": method_sha, "preflight_sha256": sha(PREFLIGHT),
        "receipt_contract": context, "receipt_provenance": provenance,
        "population": {"pixels": int(valid.sum()), "positive_pixels": int(truth.sum()),
                       "validation_supervision_overlap": 0, "spatial_blocks": len(block_indices)},
        "model_auc": model_auc, "model_average_precision": ap_uint8(scores, truth),
        "evaluation_mask_distance_auc": geometry_auc,
        "boundary_strata": strata,
        "within_strata_model_auc_pair_weighted": within_strata_auc,
        "within_strata_included_pixels": included_pixels,
        "within_strata_omitted_pixels": int(valid.sum()) - included_pixels,
        "within_strata_included_positive_negative_pairs": pairs_total,
        "within_block_shuffle_null": {"replicates": len(null_aucs), "seed": 20260930,
                                      "q025_q50_q975": np.quantile(null_aucs, [0.025, 0.5, 0.975]).tolist(),
                                      "min_max": [float(min(null_aucs)), float(max(null_aucs))],
                                      "upper_tail_p_monte_carlo": (1 + sum(v >= model_auc for v in null_aucs)) / 200},
        "spatial_block_bootstrap": {"replicates": 512, "valid_replicates": len(bootstrap),
                                    "degenerate_replicates": degenerate, "seed": 20260930,
                                    "auc_q025_q50_q975": np.quantile(bootstrap, [0.025, 0.5, 0.975]).tolist()},
        "claim_ceiling": method["interpretation_limit"],
    }
    write_new(RESULT, document)
    print(json.dumps({"state": document["state"], "model_auc": model_auc,
                      "geometry_auc": geometry_auc, "within_strata_model_auc": within_strata_auc,
                      "null": document["within_block_shuffle_null"],
                      "bootstrap": document["spatial_block_bootstrap"]}))


if __name__ == "__main__":
    run()
