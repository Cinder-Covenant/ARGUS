"""Verify the pinned Hecate 9.6 µm runtime without running inference."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

PROVIDER_BLOB_SHA1 = "a2d3494361d81107d4bd9268cfe377d80f22cd0a"
PROVIDER_REVISION = "9cb86e500e944b11a06a7020403cde5dffb5bcb2"
CHECKPOINT_SHA256 = "809f4f10f7cb7afa19b4bee0f7d2ab31edd7e11b664f9f210cc9c17f22fcfe5d"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_sha1(path: Path) -> str:
    payload = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(payload) + payload).hexdigest()


def resource_sample(c_root: Path, t_root: Path) -> dict:
    import psutil

    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.free,temperature.gpu,name",
         "--format=csv,noheader,nounits"], capture_output=True, text=True,
        timeout=8, check=True)
    fields = [field.strip() for field in result.stdout.strip().split(",", maxsplit=2)]
    if len(fields) != 3:
        raise RuntimeError("nvidia-smi did not return free memory, temperature and GPU name")
    import shutil

    return {
        "ram_available_gib": psutil.virtual_memory().available / 1024**3,
        "whole_gpu_free_mib": int(fields[0]),
        "gpu_temp_c": int(fields[1]),
        "gpu_name": fields[2],
        "c_free_gib": shutil.disk_usage(c_root).free / 1024**3,
        "t_free_gib": shutil.disk_usage(t_root).free / 1024**3,
    }


def verify(runtime_python: Path, provider_path: Path, checkpoint_path: Path,
           receipt_path: Path, c_root: Path, t_root: Path) -> dict:
    runtime_python, provider_path = runtime_python.resolve(), provider_path.resolve()
    checkpoint_path, receipt_path = checkpoint_path.resolve(), receipt_path.resolve()
    if Path(sys.executable).resolve() != runtime_python:
        raise RuntimeError("launch this script with --runtime-python as the active interpreter")
    if receipt_path.exists():
        raise FileExistsError(f"refusing to overwrite runtime receipt: {receipt_path}")
    if git_blob_sha1(provider_path) != PROVIDER_BLOB_SHA1:
        raise ValueError("provider source does not match pinned upstream Git blob")
    if file_sha256(checkpoint_path) != CHECKPOINT_SHA256:
        raise ValueError("checkpoint does not match pinned Hecate 9.6 µm SHA-256")

    before = resource_sample(c_root, t_root)
    if (before["ram_available_gib"] < 10 or before["whole_gpu_free_mib"] < 1280 or
            before["gpu_temp_c"] >= 70 or before["c_free_gib"] < 50 or
            before["t_free_gib"] < 85):
        raise RuntimeError(f"strict-load resource admission refused: {before}")

    # The project guard supplies single-flight admission, thermal/RAM/VRAM
    # watchdogs and a two-thread CPU cap. This is model load only, no inference.
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    sys.path.insert(0, str(repo_root / "scripts"))
    import resource_guard
    resource_guard.admit("hecate_strict_load", need_ram_gb=1.0,
                         need_vram_gb=0.8, single_flight=True)
    admitted = True
    started = time.perf_counter()
    try:
        for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                     "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
            os.environ[name] = "2"
        import torch

        torch.set_num_threads(2)
        torch.set_num_interop_threads(2)
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable in the selected runtime")
        free, _ = torch.cuda.mem_get_info(0)
        if free / 1024**2 < 1280:
            raise RuntimeError("whole-GPU reserve fell below 1.25 GiB before model load")
        torch.cuda.set_per_process_memory_fraction(0.5, 0)

        spec = importlib.util.spec_from_file_location("argus_pinned_hecate_strict_load", provider_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot import pinned Hecate provider")
        provider = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(provider)
        model = provider.load_model(str(checkpoint_path), "cuda")
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - started
        if tuple(model.patch_size) != (16, 64, 64) or float(model.sampling_um) != 9.6:
            raise RuntimeError("loaded model does not satisfy the pinned 9.6 µm input contract")
        after = resource_sample(c_root, t_root)
        if (after["ram_available_gib"] < 8 or after["whole_gpu_free_mib"] < 1280 or
                after["gpu_temp_c"] >= 70):
            raise RuntimeError(f"strict-load postcondition failed: {after}")
        receipt = {
            "schema": "argus-hecate-runtime-receipt-v1",
            "state": "STRICT_LOAD_PASSED",
            "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "revision": PROVIDER_REVISION,
            "source": {"path": str(provider_path), "git_blob_sha1": PROVIDER_BLOB_SHA1,
                       "sha256": file_sha256(provider_path)},
            "checkpoint": {"path": str(checkpoint_path), "sha256": CHECKPOINT_SHA256,
                           "variant": "9.6um"},
            "runtime": {"python_executable": str(runtime_python), "python": platform.python_version(),
                        "torch": torch.__version__, "device": "cuda", "sampling_um": 9.6,
                        "patch_size": [16, 64, 64], "parameters": int(sum(p.numel() for p in model.parameters())),
                        "strict_load_seconds": round(elapsed, 3), "gpu": after["gpu_name"]},
            "resources": {"before": before, "after": after,
                          "limits": {"minimum_admission_ram_gib": 10,
                                     "hard_ram_floor_gib": 8,
                                     "minimum_whole_gpu_free_mib": 1280,
                                     "maximum_gpu_temp_c": 70,
                                     "minimum_c_free_gib": 50,
                                     "minimum_t_free_gib": 85,
                                     "cuda_allocator_fraction": 0.5,
                                     "cpu_threads": 2}},
            "execution": {"inference": False, "training": False, "target_search": False},
            "claim_ceiling": "runtime strict-load only; no inference ran and no scientific claim is established",
        }
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        with receipt_path.open("x", encoding="utf-8") as output:
            json.dump(receipt, output, indent=2)
            output.write("\n")
        return receipt
    finally:
        if admitted:
            resource_guard.release_lock()
            resource_guard.deregister_job()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-python", type=Path, required=True)
    parser.add_argument("--provider", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True,
                        help="new local output file; an existing receipt is never overwritten")
    parser.add_argument("--c-root", type=Path, default=Path("C:/"))
    parser.add_argument("--t-root", type=Path, default=Path("T:/"))
    args = parser.parse_args()
    result = verify(args.runtime_python, args.provider, args.checkpoint,
                    args.receipt, args.c_root, args.t_root)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
