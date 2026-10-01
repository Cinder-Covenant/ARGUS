"""Run ARGUS's fixed retained PHerc0139 Hecate apparatus control.

This is intentionally not a general inference CLI. Its only accepted input and
outputs are the configured, hash-bound PHerc0139 development-control artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
HELPER = ROOT / "argus" / "core" / "hecate_shared_output.py"
PROVIDER_BLOB = "a2d3494361d81107d4bd9268cfe377d80f22cd0a"
CHECKPOINT_SHA = "809f4f10f7cb7afa19b4bee0f7d2ab31edd7e11b664f9f210cc9c17f22fcfe5d"
LOCAL_CONTROL_ID = "local-control-0139-title-native9362"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def blob_sha1(path: Path) -> str:
    body = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(body) + body).hexdigest()  # Git blob identity


def files_manifest(root: Path) -> list[dict]:
    return [{"path": p.relative_to(root).as_posix(), "bytes": p.stat().st_size,
             "sha256": sha(p)} for p in sorted(root.rglob("*")) if p.is_file()]


def repo_artifact_path(path: Path, artifact_root: Path) -> str:
    """Encode an output using the configured repo artifact convention."""
    try:
        relative = path.resolve().relative_to(artifact_root.resolve())
    except ValueError as exc:
        raise ValueError("Hecate output is outside the configured artifact root") from exc
    return "artifacts/" + relative.as_posix()


def _replace_progress_file(temp: Path, destination: Path, *, attempts: int = 20,
                          retry_delay_s: float = 0.05) -> None:
    """Retry atomic progress replacement while the Windows monitor releases a read handle."""
    for attempt in range(attempts):
        try:
            os.replace(temp, destination)
            return
        except PermissionError:
            if attempt + 1 >= attempts:
                raise
            time.sleep(retry_delay_s)


class ControlledStop(RuntimeError):
    pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-id", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--preparation", required=True)
    ap.add_argument("--provider", required=True)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--runtime-receipt", required=True)
    ap.add_argument("--output-png", required=True)
    ap.add_argument("--output-zarr", required=True)
    ap.add_argument("--progress-file", required=True)
    ap.add_argument("--pause-file", required=True)
    ap.add_argument("--stop-file", required=True)
    ns = ap.parse_args()

    from argus.core import hecate_candidate as candidate
    artifact_root = candidate.paths.artifact_write_root().resolve()
    input_path = candidate._CONTROL_INPUT.resolve()
    preparation_path = candidate._CONTROL_PREPARATION.resolve()
    provider_path = candidate._CONTROL_PROVIDER.resolve()
    checkpoint_path = candidate._CONTROL_CHECKPOINT.resolve()
    runtime_receipt = candidate._CONTROL_RUNTIME_RECEIPT.resolve()
    if (not ns.job_id.startswith("job_") or Path(ns.input).resolve() != input_path or
            Path(ns.preparation).resolve() != preparation_path or
            Path(ns.provider).resolve() != provider_path or
            Path(ns.checkpoint).resolve() != checkpoint_path or
            Path(ns.runtime_receipt).resolve() != runtime_receipt):
        raise RuntimeError("only the configured, pinned PHerc0139 control material is permitted")
    png = Path(ns.output_png).resolve()
    zarr_path = Path(ns.output_zarr).resolve()
    run_dir = png.parent
    if (not run_dir.is_dir() or run_dir.parent != artifact_root or
            not run_dir.name.startswith("hecate_control_pherc0139_") or
            png.name != "prediction.png" or zarr_path != run_dir / "prediction_3d.zarr"):
        raise RuntimeError("output paths are outside the fresh canonical control run")
    if (run_dir / "RUN_RECEIPT.json").exists() or png.exists() or zarr_path.exists():
        raise FileExistsError("this control run has already produced output")
    if not input_path.is_file() or not preparation_path.is_file() or not runtime_receipt.is_file():
        raise FileNotFoundError("the retained preparation or pinned runtime receipt is missing")

    import numpy as np
    import psutil
    import torch
    import zarr
    from PIL import Image

    preparation = json.loads(preparation_path.read_text(encoding="utf-8"))
    if preparation.get("state") != "PREPARED_RETAINED_EXPOSED_CONTROL" or \
            preparation.get("physical_scroll") != "PHerc0139" or \
            preparation.get("acquisition_id") != LOCAL_CONTROL_ID or \
            preparation.get("input", {}).get("sha256") != candidate.CONTROL_INPUT_SHA256 or \
            preparation.get("input", {}).get("array_sha256") != candidate.CONTROL_ARRAY_SHA256 or \
            preparation.get("input", {}).get("shape_zyx") != list(candidate.CONTROL_ARRAY_SHAPE) or \
            preparation.get("input", {}).get("dtype") != "uint8" or \
            preparation.get("input", {}).get("spacing_um") != [9.6, 9.6, 9.6] or \
            sha(input_path) != candidate.CONTROL_INPUT_SHA256:
        raise RuntimeError("the prepared input no longer matches its retained-control receipt")
    if blob_sha1(provider_path) != PROVIDER_BLOB or sha(checkpoint_path) != CHECKPOINT_SHA:
        raise RuntimeError("pinned Hecate provider or checkpoint changed")
    runtime = json.loads(runtime_receipt.read_text(encoding="utf-8"))
    if runtime.get("state") != "STRICT_LOAD_PASSED":
        raise RuntimeError("the pinned Hecate runtime has no strict-load pass")
    runtime_hash = sha(runtime_receipt)

    from argus.core import hecate_shared_output
    if sha(HELPER) != os.environ.get("ARGUS_HECATE_HELPER_SHA256"):
        raise RuntimeError("shared-output helper differs from the reviewed plan")
    if sha(Path(__file__)) != os.environ.get("ARGUS_HECATE_RUNNER_SHA256"):
        raise RuntimeError("runner source differs from the reviewed plan")

    if psutil.virtual_memory().available / 1024**3 < 10:
        raise RuntimeError("RAM admission floor is below 10 GiB")
    if (shutil_free_gib(Path(Path.home().anchor or "/")) < 50 or
            shutil_free_gib(Path(artifact_root.anchor or "/")) < 85):
        raise RuntimeError("output/system run-start disk reserve was not met")
    free, _ = torch.cuda.mem_get_info(0)
    if free / 1024**3 < 1.25:
        raise RuntimeError("whole-GPU free-memory floor is below 1.25 GiB")

    # Keep the existing single-flight guard in the Hecate process itself.  It owns
    # the lock/reaper for this complete model lifetime and caps CPU worker threads.
    sys.path.insert(0, str(ROOT / "scripts"))
    import resource_guard
    resource_guard.admit("hecate_control_pherc0139", need_ram_gb=2.0,
                         need_vram_gb=0.8, single_flight=True)

    admitted = True
    try:
        torch.set_num_threads(2)
        torch.set_num_interop_threads(2)
        torch.cuda.set_per_process_memory_fraction(0.5, 0)
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is not available in the pinned Hecate runtime")
        spec = importlib.util.spec_from_file_location("argus_pinned_hecate_control", provider_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load pinned Hecate provider")
        provider = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(provider)
        model = provider.load_model(str(checkpoint_path), "cuda")
        if tuple(model.patch_size) != (16, 64, 64) or float(model.sampling_um) != 9.6:
            raise RuntimeError("loaded Hecate model has an unexpected 9.6-um input contract")

        progress_path = Path(ns.progress_file)
        pause_path = Path(ns.pause_file)
        stop_path = Path(ns.stop_file)

        def stopped() -> None:
            if stop_path.exists():
                raise ControlledStop(stop_path.read_text(encoding="utf-8")[:200])

        def before_batch() -> None:
            stopped()
            while pause_path.exists():
                stopped()
                time.sleep(0.25)

        def progress(done: int, total: int) -> None:
            temp = progress_path.with_suffix(".tmp")
            temp.write_text(json.dumps({"phase": "inference", "completed_tiles": done,
                                        "total_tiles": total, "updated_utc": time.strftime(
                                            "%Y-%m-%dT%H:%M:%SZ", time.gmtime())}), encoding="utf-8")
            _replace_progress_file(temp, progress_path)

        volume = np.load(input_path, mmap_mode="r", allow_pickle=False)
        if volume.shape != candidate.CONTROL_ARRAY_SHAPE or volume.dtype != np.dtype("uint8") or \
                hashlib.sha256(volume.tobytes(order="C")).hexdigest() != candidate.CONTROL_ARRAY_SHA256:
            raise RuntimeError("prepared pixels differ from the fixed exposed-control array")
        output2 = np.lib.format.open_memmap(run_dir / "prediction_2d.npy", mode="w+",
                                            dtype=np.uint8, shape=(256, 256))
        output3 = np.lib.format.open_memmap(run_dir / "prediction_3d.npy", mode="w+",
                                            dtype=np.uint8, shape=(16, 256, 256))
        inference_started = time.perf_counter()
        details = hecate_shared_output.predict_both(
            model, volume, output2, output3, batch_size=1, stride=32, precision="fp32",
            before_batch=before_batch, progress=progress)
        torch.cuda.synchronize()
        inference_seconds = time.perf_counter() - inference_started
        stopped()
        output2.flush(); output3.flush()
        Image.fromarray(np.asarray(output2), mode="L").save(png, format="PNG")
        zarr_array = zarr.open(str(zarr_path), mode="w", shape=(16, 256, 256),
                               chunks=(1, 64, 64), dtype="u1")
        zarr_array[:] = np.asarray(output3)
        zarr_array.attrs.update({"physical_scroll": "PHerc0139", "acquisition_id": LOCAL_CONTROL_ID,
                                 "spacing_um": [9.6, 9.6, 9.6], "axes": ["z", "y", "x"],
                                 "provider_revision": "9cb86e500e944b11a06a7020403cde5dffb5bcb2"})
        del output2, output3
        for temp in (run_dir / "prediction_2d.npy", run_dir / "prediction_3d.npy"):
            temp.unlink(missing_ok=True)

        outputs_manifest = files_manifest(zarr_path)
        # Viewer receipts use the project artifact convention even when the
        # installed source tree and configured ARGUS_REPO live in different roots.
        output_rel_png = repo_artifact_path(png, artifact_root)
        output_rel_zarr = repo_artifact_path(zarr_path, artifact_root)
        decoded = np.asarray(Image.open(png).convert("L"))
        source = preparation["source"]
        receipt = {
            "schema": "argus-hecate-control-run-v1", "run_id": ns.job_id,
            "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "terminal": "COMPLETE", "operational_state": "COMPLETE",
            "physical_scroll": "PHerc0139", "acquisition_id": LOCAL_CONTROL_ID,
            "segment": "retained-256x256-control-field",
            "provider": "hecate_96um", "provider_revision": "9cb86e500e944b11a06a7020403cde5dffb5bcb2",
            "runtime_receipt": {"path": str(runtime_receipt), "sha256": runtime_hash},
            "preparation": {"path": str(preparation_path),
                            "sha256": sha(preparation_path), "input_path": str(input_path),
                            "input_sha256": sha(input_path), "source": source},
            "paired_orientation_control": {"decision_rule": "one forward apparatus output only; orientation and construction trust were not evaluated",
                                            "construction_trust": "NOT_EVALUATED_SINGLE_FORWARD_CONTROL"},
            "outputs": {"images": {"forward": {"path": output_rel_png, "sha256": sha(png),
                                                  "min": int(decoded.min()), "max": int(decoded.max()),
                                                  "mean": float(decoded.mean())}},
                        "forward_3d": {"path": output_rel_zarr, "files": outputs_manifest,
                                        "manifest_sha256": hashlib.sha256(json.dumps(outputs_manifest, sort_keys=True,
                                                                                     separators=(",", ":")).encode()).hexdigest()}},
            "execution": {"input_shape_zyx": [16, 256, 256], "spacing_um": [9.6, 9.6, 9.6],
                          "batch_size": 1, "stride": 32, "precision": "fp32", "tile_count": details["tile_count"],
                          "elapsed_inference_seconds": inference_seconds,
                          "helper_path": str(HELPER), "helper_sha256": sha(HELPER),
                          "runner_path": str(Path(__file__).resolve()), "runner_sha256": sha(Path(__file__))},
            "exposure": "EXPOSED_DIRECT", "scientific_state": "APPARATUS_CONTROL_PASSED",
            "eligible_for_automatic_routing": False,
            "claim_ceiling": "one retained PHerc0139 exposed-control run; operational parity/display only; no target inference, ink-accuracy, generalization or reading claim",
        }
        (run_dir / "RUN_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        progress_path.write_text(json.dumps({"phase": "complete", "completed_tiles": details["tile_count"],
                                             "total_tiles": details["tile_count"], "updated_utc": receipt["recorded_utc"]}),
                                 encoding="utf-8")
        print(json.dumps({"status": "COMPLETE", "receipt": "artifacts/" + run_dir.name + "/RUN_RECEIPT.json",
                          "png_sha256": sha(png), "zarr_manifest_sha256": receipt["outputs"]["forward_3d"]["manifest_sha256"],
                          "tiles": details["tile_count"]}))
        return 0
    finally:
        if admitted:
            resource_guard.release_lock()
            resource_guard.deregister_job()


def shutil_free_gib(path: Path) -> float:
    import shutil
    return shutil.disk_usage(path).free / 1024**3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ControlledStop as exc:
        print("CONTROLLED_STOP: " + str(exc), file=sys.stderr)
        raise SystemExit(20)
