"""Pinned Hecate plan plus the one fixed PHerc0139 apparatus-control executor.

General Hecate requests remain plan-only.  ``run_control`` accepts only the
retained, hash-bound PHerc0139 development-control field; it is not a target
detector door and cannot be pointed at another input or output path.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
import time
from pathlib import Path

from argus.core import paths, science_candidates, scroll_ids

SCHEMA = "argus-hecate-plan-v1"
SOURCE_REVISION = "9cb86e500e944b11a06a7020403cde5dffb5bcb2"
SOURCE_BLOB_SHA1 = "a2d3494361d81107d4bd9268cfe377d80f22cd0a"
CONTROL_ID = "local-control-0139-title-native9362"
CONTROL_INPUT_SHA256 = "3bdfab85fed733757ed3a0021f6240e02afb9bda9af9a12a7ef67c5ae156eb86"
CONTROL_ARRAY_SHA256 = "b7d2f762e67031302eb55420851c4236e5d11696ff26639d1915bcdc94208ca6"
CONTROL_ARRAY_SHAPE = (16, 256, 256)
_ROOT = Path(__file__).resolve().parents[2]
_CONTROL_INPUT = Path(os.environ.get(
    "ARGUS_HECATE_CONTROL_INPUT", paths.science_data("controls", "pherc0139", "control_field_input.npy")))
_CONTROL_PREPARATION = Path(os.environ.get(
    "ARGUS_HECATE_CONTROL_PREPARATION", _CONTROL_INPUT.with_name("PREPARATION.json")))
_CONTROL_RUNNER = _ROOT / "scripts" / "hecate_control_runner.py"
_CONTROL_HELPER = _ROOT / "argus" / "core" / "hecate_shared_output.py"
_CONTROL_RUNTIME = Path(os.environ.get("ARGUS_HECATE_RUNTIME", paths.villa_runtime("Scripts", "python.exe")))
_CONTROL_PROVIDER = Path(os.environ.get(
    "ARGUS_HECATE_PROVIDER", paths.upstream("hecate", SOURCE_REVISION, "hecate.py")))
_CONTROL_CHECKPOINT = _CONTROL_PROVIDER.with_name("hecate_9.6um.pth")
_CONTROL_RUNTIME_RECEIPT = Path(os.environ.get(
    "ARGUS_HECATE_RUNTIME_RECEIPT", paths.runs("hecate_runtime", "RECEIPT.json")))
_CONTROL_RUN_PREFIX = "hecate_control_pherc0139_"


class HecatePlanRefusal(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_blob_id(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()  # noqa: S324 - Git object id


def _run_artifact_dir(outputs: dict) -> Path | None:
    """Only a fresh, named control run immediately under the canonical artifact root."""
    try:
        png = Path(outputs["png"]).resolve()
        zarr_path = Path(outputs["volume"]).resolve()
        root = png.parent
        if (not re.fullmatch(_CONTROL_RUN_PREFIX + r"[0-9a-f]{12}", root.name) or
                root.parent != paths.artifact_write_root().resolve() or root.exists() or
                png.name != "prediction.png" or
                zarr_path != root / "prediction_3d.zarr"):
            return None
        return root
    except (KeyError, TypeError, ValueError, OSError):
        return None


def control_request() -> dict:
    """Offer a newly named exposed control only when its configured local inputs exist."""
    required = (_CONTROL_INPUT, _CONTROL_PREPARATION, _CONTROL_RUNTIME,
                _CONTROL_PROVIDER, _CONTROL_CHECKPOINT, _CONTROL_RUNTIME_RECEIPT,
                _CONTROL_RUNNER, _CONTROL_HELPER, _ROOT / "scripts" / "resource_guard.py")
    missing = [p.name for p in required if not p.is_file()]
    if missing:
        return {"available": False, "why": "Configure the retained PHerc0139 Hecate control: missing " +
                ", ".join(missing)}
    run_dir = paths.artifact_write_root() / (_CONTROL_RUN_PREFIX + secrets.token_hex(6))
    return {"available": True, "request": {
        "scroll": "PHerc0139", "acquisition_id": CONTROL_ID,
        "input_render": str(_CONTROL_INPUT.resolve()), "spacing_um": 9.6,
        "python_executable": str(_CONTROL_RUNTIME.resolve()),
        "source_script": str(_CONTROL_PROVIDER.resolve()),
        "checkpoint": str(_CONTROL_CHECKPOINT.resolve()),
        "output_png": str(run_dir / "prediction.png"),
        "output_3d": str(run_dir / "prediction_3d.zarr"),
        "array": "0", "device": "cuda", "reverse": False,
        "batch_size": 1, "stride": 32, "precision": "fp32"}}


def retained_control_binding(plan: dict) -> dict | None:
    """Return the immutable implementation/input binding only for our one fixed control."""
    try:
        material = plan["material"]
        inputs = plan["inputs"]
        outputs = plan["outputs"]
        run_dir = _run_artifact_dir(outputs)
        if run_dir is None:
            return None
        png = run_dir / "prediction.png"
        zarr_path = run_dir / "prediction_3d.zarr"
        expected_argv = [str(_CONTROL_RUNTIME.resolve()), str(_CONTROL_PROVIDER.resolve()),
                         "--checkpoint", str(_CONTROL_CHECKPOINT.resolve()),
                         "--input", str(_CONTROL_INPUT.resolve()), "--array", "0",
                         "--spacing-um", "9.6", "--device", "cuda", "--batch-size", "1",
                         "--precision", "fp32", "--output", str(png),
                         "--output-3d", str(zarr_path), "--stride", "32"]
        if (plan.get("provider") != "hecate_96um" or
                material.get("physical_scroll") != "PHerc0139" or
                material.get("acquisition_id") != CONTROL_ID or
                abs(float(material.get("surface_render_spacing_um", 0)) - 9.6) > 1e-6 or
                Path(inputs.get("surface_render", "")).resolve() != _CONTROL_INPUT.resolve() or
                inputs.get("array") != "0" or
                Path(inputs.get("checkpoint", "")).resolve() != _CONTROL_CHECKPOINT.resolve() or
                Path((plan.get("runtime") or {}).get("python_executable", "")).resolve() !=
                _CONTROL_RUNTIME.resolve() or
                (plan.get("runtime") or {}).get("device") != "cuda" or
                Path(outputs.get("png", "")).resolve() != png or
                Path(outputs.get("volume", "")).resolve() != zarr_path or
                plan.get("argv") != expected_argv or
                plan.get("source_blob_sha1") != SOURCE_BLOB_SHA1):
            return None
        if _sha256(_CONTROL_INPUT) != CONTROL_INPUT_SHA256:
            return None
        import numpy as np
        volume = np.load(_CONTROL_INPUT, mmap_mode="r", allow_pickle=False)
        if volume.shape != CONTROL_ARRAY_SHAPE or volume.dtype != np.dtype("uint8"):
            return None
        if hashlib.sha256(volume.tobytes(order="C")).hexdigest() != CONTROL_ARRAY_SHA256:
            return None
        preparation = json.loads(_CONTROL_PREPARATION.read_text(encoding="utf-8"))
        if (preparation.get("state") != "PREPARED_RETAINED_EXPOSED_CONTROL" or
                preparation.get("physical_scroll") != "PHerc0139" or
                preparation.get("acquisition_id") != CONTROL_ID or
                preparation.get("input", {}).get("sha256") != CONTROL_INPUT_SHA256 or
                preparation.get("input", {}).get("array_sha256") != CONTROL_ARRAY_SHA256 or
                preparation.get("input", {}).get("shape_zyx") != list(CONTROL_ARRAY_SHAPE) or
                preparation.get("input", {}).get("dtype") != "uint8" or
                preparation.get("input", {}).get("spacing_um") != [9.6, 9.6, 9.6]):
            return None
        if _sha256(_CONTROL_CHECKPOINT) != inputs.get("checkpoint_sha256"):
            return None
        if _git_blob_id(_CONTROL_PROVIDER) != SOURCE_BLOB_SHA1:
            return None
        return {
            "scope": "single retained PHerc0139 exposed-control field; no eligible-target execution",
            "control_id": CONTROL_ID,
            "preparation_sha256": _sha256(_CONTROL_PREPARATION),
            "input_sha256": _sha256(_CONTROL_INPUT),
            "helper_sha256": _sha256(_CONTROL_HELPER),
            "runner_sha256": _sha256(_CONTROL_RUNNER),
            "runner": str(_CONTROL_RUNNER.resolve()),
            "run_dir": str(run_dir),
            "runtime_receipt_sha256": _sha256(_CONTROL_RUNTIME_RECEIPT),
        }
    except (OSError, KeyError, TypeError, ValueError):
        return None


def is_retained_control_plan(plan: dict) -> bool:
    return retained_control_binding(plan) is not None


def _controlled_resource_sample() -> dict:
    """One host sample for the job supervisor; failures are fail-closed."""
    import psutil
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.free,temperature.gpu",
         "--format=csv,noheader,nounits"], capture_output=True, text=True,
        timeout=4, check=True)
    values = [int(v.strip()) for v in result.stdout.strip().split(",")]
    if len(values) != 2:
        raise RuntimeError("nvidia-smi did not return free VRAM and temperature")
    import shutil
    system_drive = Path.home().anchor or "/"
    output_drive = paths.artifact_write_root().anchor or "/"
    return {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ram_available_gib": psutil.virtual_memory().available / 1024**3,
            "whole_gpu_free_gib": values[0] / 1024,
            "gpu_temp_c": values[1],
            "c_free_gib": shutil.disk_usage(system_drive).free / 1024**3,
            "t_free_gib": shutil.disk_usage(output_drive).free / 1024**3}


def run_control(plan: dict, *, job_id: str, progress=None, cancelled=None) -> dict:
    """Execute one approved fixed PHerc0139 control plan and write its viewer receipt."""
    binding = retained_control_binding(plan)
    if binding is None or plan.get("argus_control_binding") != binding:
        raise HecatePlanRefusal("the request is not the current fixed PHerc0139 control plan")
    if not job_id or not job_id.startswith("job_"):
        raise HecatePlanRefusal("the governed job id is missing")
    run_dir = Path(binding["run_dir"])
    import psutil
    import shutil
    import threading

    start = _controlled_resource_sample()
    if (start["ram_available_gib"] < 10 or start["whole_gpu_free_gib"] < 1.25 or
            start["gpu_temp_c"] >= 70 or start["c_free_gib"] < 50 or start["t_free_gib"] < 85):
        raise HecatePlanRefusal("resource admission floor not met: %s" % start)
    # The command-service lease and this long-lived resource-guard lease are
    # independent protections; the subprocess also runs resource_guard.admit.
    from argus.core import actions as A
    resource_guard = _ROOT / "scripts" / "resource_guard.py"
    if not resource_guard.is_file():
        raise HecatePlanRefusal("shared single-flight resource guard is missing")

    run_token = job_id
    progress_path = run_dir / (run_token + ".progress.json")
    pause_path = run_dir / (run_token + ".pause")
    stop_path = run_dir / (run_token + ".stop")
    monitor_path = run_dir / (run_token + ".resources.jsonl")
    log_path = run_dir / (run_token + ".stdout.log")
    for path in (progress_path, pause_path, stop_path, monitor_path, log_path):
        if path.exists():
            raise HecatePlanRefusal("job-owned control output already exists; refusing overwrite")
    run_dir.mkdir(parents=True, exist_ok=False)

    env = os.environ.copy()
    for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        env[key] = "2"
    env.update({"ARGUS_HECATE_HELPER_SHA256": binding["helper_sha256"],
                "ARGUS_HECATE_RUNNER_SHA256": binding["runner_sha256"]})
    argv = [str(_CONTROL_RUNTIME), str(_CONTROL_RUNNER), "--job-id", job_id,
            "--input", str(_CONTROL_INPUT), "--preparation", str(_CONTROL_PREPARATION),
            "--provider", str(_CONTROL_PROVIDER), "--checkpoint", str(_CONTROL_CHECKPOINT),
            "--runtime-receipt", str(_CONTROL_RUNTIME_RECEIPT),
            "--output-png", str(run_dir / "prediction.png"),
            "--output-zarr", str(run_dir / "prediction_3d.zarr"), "--progress-file", str(progress_path),
            "--pause-file", str(pause_path), "--stop-file", str(stop_path)]
    if progress:
        progress({"phase": "admitted", "completed_tiles": 0, "total_tiles": 49})
    if cancelled and cancelled():
        raise A.Refused("CANCELLED", "operator cancellation was recorded before process start",
                        executed=False)
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(argv, cwd=str(_ROOT), env=env, stdout=log,
                                stderr=subprocess.STDOUT, shell=False)
        if progress:
            progress({"phase": "started", "pid": proc.pid, "completed_tiles": 0,
                      "total_tiles": 49})
        child = psutil.Process(proc.pid)
        below_65_since = None
        last_gpu_sample = 0.0
        last_progress_mtime = 0.0
        stop_reason = None
        samples = []
        try:
            while proc.poll() is None:
                now = time.monotonic()
                try:
                    ram = psutil.virtual_memory().available / 1024**3
                except Exception as exc:
                    stop_reason = "RAM probe failed: %s" % type(exc).__name__
                    stop_path.write_text(stop_reason, encoding="utf-8")
                    break
                if now - last_gpu_sample >= 1.0:
                    try:
                        sample = _controlled_resource_sample()
                    except Exception as exc:
                        stop_reason = "GPU/temperature/disk probe failed: %s" % type(exc).__name__
                        stop_path.write_text(stop_reason, encoding="utf-8")
                        break
                    sample["ram_available_gib"] = ram
                    samples.append(sample)
                    with monitor_path.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(sample, sort_keys=True) + "\n")
                    last_gpu_sample = now
                    temp = sample["gpu_temp_c"]
                    if (ram < 8 or sample["whole_gpu_free_gib"] < 1.25 or temp >= 80 or
                            sample["c_free_gib"] < 50 or sample["t_free_gib"] < 80):
                        stop_reason = "hard resource floor breached: %s" % sample
                        stop_path.write_text(stop_reason, encoding="utf-8")
                        break
                    disk_pause = sample["t_free_gib"] < 85
                    if temp >= 70 or disk_pause:
                        pause_path.touch(exist_ok=True)
                        below_65_since = None
                    elif pause_path.exists() and temp <= 65 and not disk_pause:
                        if below_65_since is None:
                            below_65_since = now
                        elif now - below_65_since >= 10.0:
                            pause_path.unlink(missing_ok=True)
                            below_65_since = None
                    else:
                        below_65_since = None
                if cancelled and cancelled():
                    stop_reason = "cancelled by operator through the governed job action"
                    stop_path.write_text(stop_reason, encoding="utf-8")
                    if pause_path.exists():
                        pause_path.unlink(missing_ok=True)
                if progress_path.is_file():
                    stat = progress_path.stat()
                    if stat.st_mtime > last_progress_mtime:
                        last_progress_mtime = stat.st_mtime
                        try:
                            state = json.loads(progress_path.read_text(encoding="utf-8"))
                            if progress:
                                progress({**state, "pid": proc.pid})
                        except (ValueError, OSError):
                            pass
                time.sleep(0.5)
        finally:
            if proc.poll() is None and stop_reason:
                try:
                    proc.wait(timeout=6)
                except subprocess.TimeoutExpired:
                    for p in reversed([child] + child.children(recursive=True)):
                        try:
                            p.terminate()
                        except psutil.Error:
                            pass
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill(); proc.wait(timeout=3)
        return_code = proc.wait()
    if stop_reason:
        raise A.Refused("CANCELLED" if "cancelled by operator" in stop_reason else "RESOURCE_STOP",
                        stop_reason, executed=True, monitor=str(monitor_path))
    if return_code != 0:
        detail = log_path.read_text(encoding="utf-8", errors="replace")[-1600:]
        raise A.Refused("HECATE_CONTROL_FAILED", "runner exited %d: %s" % (return_code, detail),
                        executed=True, log=str(log_path))
    receipt_path = run_dir / "RUN_RECEIPT.json"
    if not receipt_path.is_file():
        raise A.Refused("HECATE_RECEIPT_MISSING", "runner exited zero without a control receipt",
                        executed=True, log=str(log_path))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("run_id") != job_id or receipt.get("physical_scroll") != "PHerc0139":
        raise A.Refused("HECATE_RECEIPT_IDENTITY", "completed receipt failed its identity check",
                        executed=True)
    if progress:
        progress({"phase": "complete", "completed_tiles": 49, "total_tiles": 49,
                  "receipt": "artifacts/" + run_dir.name + "/RUN_RECEIPT.json"})
    return {"status": "OK", "executed": True,
            "receipt": "artifacts/" + run_dir.name + "/RUN_RECEIPT.json",
            "png_sha256": receipt["outputs"]["images"]["forward"]["sha256"],
            "zarr_manifest_sha256": receipt["outputs"]["forward_3d"]["manifest_sha256"],
            "resource_monitor": "artifacts/" + run_dir.name + "/" + monitor_path.name,
            "log": "artifacts/" + run_dir.name + "/" + log_path.name}


def _candidate(spacing_um: float) -> dict:
    target = "hecate_24um" if abs(spacing_um - 2.4) <= 0.048 else (
        "hecate_96um" if abs(spacing_um - 9.6) <= 0.192 else None)
    if target is None:
        raise HecatePlanRefusal("spacing_um must match a released 2.4 or 9.6 um checkpoint within 2%")
    return next(row for row in science_candidates.inventory()["candidates"] if row["id"] == target)


def plan(*, scroll: str, acquisition_id: str, input_render: str, spacing_um: float,
         python_executable: str, source_script: str, checkpoint: str, output_png: str | None = None,
         output_3d: str | None = None, array: str = "0", device: str = "cuda",
         reverse: bool = False, batch_size: int = 1, stride: int | None = None,
         precision: str = "fp32") -> dict:
    try:
        canonical = scroll_ids.resolve(scroll)
    except KeyError as exc:
        raise HecatePlanRefusal(str(exc)) from None
    if not acquisition_id.strip():
        raise HecatePlanRefusal("acquisition_id is required")
    candidate = _candidate(float(spacing_um))
    runtime = Path(python_executable).resolve()
    source = Path(source_script).resolve()
    weights = Path(checkpoint).resolve()
    volume = Path(input_render).resolve()
    if not runtime.is_file():
        raise HecatePlanRefusal("python_executable must be an existing explicit interpreter path")
    if not source.is_file() or _git_blob_id(source) != SOURCE_BLOB_SHA1:
        raise HecatePlanRefusal("hecate.py is absent or differs from the pinned source blob")
    if not weights.is_file() or _sha256(weights) != candidate["artifact"]["sha256"]:
        raise HecatePlanRefusal("checkpoint is absent or differs from the pinned SHA-256")
    if not volume.exists() or not (volume.suffix.lower() == ".npy" or
                                   (volume.is_dir() and volume.suffix.lower() == ".zarr")):
        raise HecatePlanRefusal("input_render must be an existing uint8 ZYX .npy or local Zarr directory")
    if not output_png and not output_3d:
        raise HecatePlanRefusal("at least one of output_png or output_3d is required")
    outputs: dict[str, str] = {}
    for name, raw, suffix in (("png", output_png, ".png"), ("volume", output_3d, ".zarr")):
        if not raw:
            continue
        path = Path(raw).resolve()
        if path.suffix.lower() != suffix or path.exists():
            raise HecatePlanRefusal("%s output must be a new %s path" % (name, suffix))
        if name == "png" and path.with_suffix(".json").exists():
            raise HecatePlanRefusal("PNG metadata output already exists; plans never overwrite")
        outputs[name] = str(path)
    if precision not in {"fp32", "bf16"}:
        raise HecatePlanRefusal("precision must be fp32 or bf16")
    if batch_size < 1 or (stride is not None and stride < 1):
        raise HecatePlanRefusal("batch_size and explicit stride must be positive")
    argv = [str(runtime), str(source), "--checkpoint", str(weights), "--input", str(volume),
            "--array", array, "--spacing-um", str(float(spacing_um)), "--device", device,
            "--batch-size", str(int(batch_size)), "--precision", precision]
    if output_png:
        argv += ["--output", outputs["png"]]
    if output_3d:
        argv += ["--output-3d", outputs["volume"]]
    if reverse:
        argv.append("--reverse")
    if stride is not None:
        argv += ["--stride", str(int(stride))]
    selected_candidates = science_candidates.inventory(canonical)["candidates"]
    selected = next(row for row in selected_candidates if row["id"] == candidate["id"])
    payload = {
        "schema": SCHEMA, "state": "PLANNED_PROVIDER_EXECUTION", "read_only": True,
        "provider": candidate["id"], "source_revision": SOURCE_REVISION,
        "source_blob_sha1": SOURCE_BLOB_SHA1,
        "material": {"physical_scroll": canonical, "acquisition_id": acquisition_id,
                     "surface_render_spacing_um": float(spacing_um)},
        "runtime": {"python_executable": str(runtime), "device": device},
        "inputs": {"surface_render": str(volume), "array": array,
                   "checkpoint": str(weights), "checkpoint_sha256": candidate["artifact"]["sha256"]},
        "outputs": outputs, "argv": argv,
        "scientific_state": "CANDIDATE_CONTROL_REQUIRED",
        "exposure": selected["selected_scroll_exposure"],
        "promotion": "never automatic; strict-load, known-label and independent-control receipts required",
    }
    payload["plan_sha256"] = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return payload
