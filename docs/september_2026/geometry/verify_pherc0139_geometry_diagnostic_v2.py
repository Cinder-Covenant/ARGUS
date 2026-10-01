"""Exercise the v2 replay's provenance and between-phase refusal rules.

Usage:
  python verify_pherc0139_geometry_diagnostic_v2.py --root /path/to/retained

The retained root must contain the exact registered PHerc0139 w016 prediction,
label chunks and pipeline receipt. This test copies only registered inputs to
temporary directories; it performs one CPU analysis and no inference/network IO.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "pherc0139_geometry_diagnostic_v2.py"
METHOD = HERE / "METHOD_FROZEN_BEFORE_RUN.json"
REFERENCE = HERE / "REFERENCE_INPUTS_V2.json"
HISTORICAL_RESULT = HERE / "RESULT.json"
SCIENCE_FIELDS = (
    "population", "model_auc", "model_average_precision", "evaluation_mask_distance_auc",
    "boundary_strata", "within_strata_model_auc_pair_weighted", "within_strata_included_pixels",
    "within_strata_omitted_pixels", "within_strata_included_positive_negative_pairs",
    "within_block_shuffle_null", "spatial_block_bootstrap", "claim_ceiling",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(script: Path, phase: str, root: Path, output: Path, expect_success: bool, error_text: str = "") -> dict:
    result = subprocess.run(
        [sys.executable, str(script), phase, "--root", str(root), "--output-dir", str(output)],
        text=True, capture_output=True, check=False,
    )
    if expect_success and result.returncode != 0:
        raise RuntimeError(f"{phase} unexpectedly failed: {result.stderr[-2000:]}")
    if not expect_success and (result.returncode == 0 or error_text not in result.stderr):
        raise RuntimeError(f"expected refusal {error_text!r}; exit={result.returncode}; stderr={result.stderr[-2000:]}")
    return {"returncode": result.returncode, "stderr": result.stderr}


def copy_inputs(source: Path, destination: Path, reference: dict) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for relative in [*reference["scientific_input_sha256"], "PIPELINE_RUN_RECEIPT.json"]:
        src = source / Path(relative)
        dst = destination / Path(relative)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def changed_provenance(root: Path) -> tuple[str, str]:
    path = root / "PIPELINE_RUN_RECEIPT.json"
    receipt = json.loads(path.read_text(encoding="utf-8"))
    old_sha = sha(path)
    receipt["run_id"] = "20261001T000000Z-RELOCATED"
    receipt["started_utc"] = "2026-10-01T00:00:00Z"
    receipt["finished_utc"] = "2026-10-01T00:02:45Z"
    for item in receipt["stages"]:
        detail = item.get("detail", {})
        if item.get("stage") == "acquire_ct":
            detail["store"] = "relocated/cache/store"
        elif item.get("stage") == "prepare":
            detail.get("attrs", {})["source"] = "relocated/source/crop/2"
        elif item.get("stage") == "acquire_model":
            detail["path"] = "relocated/models/checkpoint.pth"
    receipt.get("sealed_crop", {})["store"] = "relocated/cache/store"
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    return old_sha, sha(path)


def expect_receipt_refusal(root: Path, output: Path, reference: dict, field: str, value) -> None:
    copy_inputs(root, output.with_name(output.name + "-root"), reference)
    copied_root = output.with_name(output.name + "-root")
    path = copied_root / "PIPELINE_RUN_RECEIPT.json"
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if field == "scroll":
        next(x for x in receipt["stages"] if x["stage"] == "identify")["detail"]["scroll"] = value
    elif field == "crop":
        next(x for x in receipt["stages"] if x["stage"] == "prepare")["detail"]["crop"]["shape"][1] += value
    elif field == "exposure":
        receipt["result_class"]["exposure_basis"] = value
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    run(SCRIPT, "preflight", copied_root, output, False,
        "receipt scroll, crop, exposure, checkpoint, or score contract changed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="argus-geometry-v2-") as temporary:
        temp = Path(temporary)

        # Preflight original bytes, then analyze from a relocated copy whose
        # arrays are identical and whose receipt paths/times/run id differ.
        valid_out = temp / "valid-output"
        run(SCRIPT, "preflight", root, valid_out, True)
        moved_root = temp / "relocated-root"
        copy_inputs(root, moved_root, reference)
        old_receipt_sha, new_receipt_sha = changed_provenance(moved_root)
        run(SCRIPT, "analyze", moved_root, valid_out, True)
        result = json.loads((valid_out / "RESULT.json").read_text(encoding="utf-8"))
        if old_receipt_sha == new_receipt_sha or result["receipt_provenance"]["receipt_sha256"] != new_receipt_sha:
            raise RuntimeError("changed receipt provenance was not recorded")
        historical = json.loads(HISTORICAL_RESULT.read_text(encoding="utf-8"))
        if any(result[key] != historical[key] for key in SCIENCE_FIELDS):
            raise RuntimeError("scientific result differs from the preserved registered result")

        # A changed prediction between phases is rejected before a result is written.
        data_out, data_root = temp / "changed-data-output", temp / "changed-data-root"
        run(SCRIPT, "preflight", root, data_out, True)
        copy_inputs(root, data_root, reference)
        with (data_root / "prediction.tif").open("ab") as stream:
            stream.write(b"changed-scientific-input")
        run(SCRIPT, "analyze", data_root, data_out, False, "retained prediction identity changed")
        if (data_out / "RESULT.json").exists():
            raise RuntimeError("changed scientific data left a result file")

        # Scroll, crop geometry and exposure changes are rejected at preflight.
        for name, field, value in (("wrong-scroll", "scroll", "PHerc0009B"),
                                   ("wrong-crop", "crop", 1),
                                   ("wrong-exposure", "exposure", "UNSEEN_SCROLL")):
            expect_receipt_refusal(root, temp / name, reference, field, value)

        # The execution source is frozen too: modifying it between phases fails.
        source_bundle = temp / "source-bundle"
        source_bundle.mkdir()
        changed_script = source_bundle / SCRIPT.name
        shutil.copy2(SCRIPT, changed_script)
        shutil.copy2(METHOD, source_bundle / METHOD.name)
        shutil.copy2(REFERENCE, source_bundle / REFERENCE.name)
        source_out = temp / "changed-source-output"
        run(changed_script, "preflight", root, source_out, True)
        with changed_script.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write("\n# source mutation used by the refusal check\n")
        run(changed_script, "analyze", root, source_out, False,
            "source, method, reference, scientific input, or receipt contract changed since preflight")
        if (source_out / "RESULT.json").exists():
            raise RuntimeError("changed source left a result file")

        # Altering the registered hash file also fails closed.
        reference_bundle = temp / "reference-bundle"
        reference_bundle.mkdir()
        reference_script = reference_bundle / SCRIPT.name
        shutil.copy2(SCRIPT, reference_script)
        shutil.copy2(METHOD, reference_bundle / METHOD.name)
        reference_copy = reference_bundle / REFERENCE.name
        shutil.copy2(REFERENCE, reference_copy)
        reference_out = temp / "changed-reference-output"
        run(reference_script, "preflight", root, reference_out, True)
        altered_reference = json.loads(reference_copy.read_text(encoding="utf-8"))
        altered_reference["scientific_input_sha256"]["prediction.tif"] = "0" * 64
        reference_copy.write_text(json.dumps(altered_reference, indent=2) + "\n", encoding="utf-8", newline="\n")
        run(reference_script, "analyze", root, reference_out, False, "registered input reference changed")
        if (reference_out / "RESULT.json").exists():
            raise RuntimeError("changed reference left a result file")

    print(json.dumps({
        "state": "PASS_GEOMETRY_V2_REPLAY_GUARDS",
        "accepted": "identical pinned prediction/label bytes with changed run id, timestamps and path fields",
        "refused": ["changed prediction between phases", "wrong physical scroll", "wrong crop shape",
                    "wrong exposure class", "source mutation between phases", "reference mutation between phases"],
        "relocated_receipt_sha256_before": old_receipt_sha,
        "relocated_receipt_sha256_after": new_receipt_sha,
        "scientific_fields_equal_to_preserved_result": list(SCIENCE_FIELDS),
        "full_analysis_runs": 1,
        "detector_inference": False,
        "network_access": False,
    }, indent=2))


if __name__ == "__main__":
    main()
