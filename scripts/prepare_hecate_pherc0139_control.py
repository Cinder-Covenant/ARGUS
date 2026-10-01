"""Prepare ARGUS's fixed, exposed PHerc0139 Hecate control from a local Zarr."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import scipy.ndimage
import zarr

CONTROL_ID = "local-control-0139-title-native9362"
EXPECTED_ARRAY_SHA256 = "b7d2f762e67031302eb55420851c4236e5d11696ff26639d1915bcdc94208ca6"
EXPECTED_NPY_SHA256 = "3bdfab85fed733757ed3a0021f6240e02afb9bda9af9a12a7ef67c5ae156eb86"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare(source_path: Path, output_dir: Path) -> dict:
    source_path = source_path.resolve()
    output_dir = output_dir.resolve()
    if not source_path.is_dir():
        raise FileNotFoundError(f"local source Zarr does not exist: {source_path}")
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite preparation output: {output_dir}")
    if (output_dir == source_path or source_path in output_dir.parents or
            output_dir in source_path.parents):
        raise ValueError("source Zarr and new output directory must not overlap")
    source = zarr.open(str(source_path), mode="r")
    array = source["0"] if hasattr(source, "keys") and "0" in source else source
    if array.ndim != 3 or array.dtype != np.dtype("uint8"):
        raise ValueError("source level 0 must be a uint8 ZYX volume")
    if tuple(array.shape) == (28, 1780, 5360):
        z_source_start = 3
    elif tuple(array.shape) == (21, 1780, 5360):
        # This is the retained 21-plane extraction of source planes [3:24).
        z_source_start = 0
    else:
        raise ValueError(f"unexpected source shape: {tuple(array.shape)}")
    attrs_path = source_path / ".zattrs"
    if not attrs_path.is_file():
        raise ValueError("source Zarr is missing its physical scale metadata")
    attrs = json.loads(attrs_path.read_text(encoding="utf-8"))
    transforms = attrs.get("multiscales", [{}])[0].get("datasets", [{}])[0].get("coordinateTransformations", [])
    spacing = next((item.get("scale") for item in transforms
                    if item.get("type") == "scale" and len(item.get("scale", [])) == 3), None)
    if spacing is None or not np.allclose(np.asarray(spacing, dtype=np.float64), [9.362] * 3, rtol=0, atol=1e-6):
        raise ValueError(f"source spacing is not the retained 9.362 um isotropic control: {spacing}")

    crop_yx = (880, 1168, 2608, 2896)
    source_crop = np.asarray(array[z_source_start:z_source_start + 21,
                                   crop_yx[0]:crop_yx[1], crop_yx[2]:crop_yx[3]], dtype=np.float32)
    if source_crop.shape != (21, 288, 288):
        raise ValueError(f"fixed control crop shape changed: {source_crop.shape}")

    ratio = 9.6 / 9.362
    z = (np.arange(16, dtype=np.float32) - 7.5) * ratio + 10.0
    y = (np.arange(256, dtype=np.float32) - 127.5) * ratio + 144.0
    x = (np.arange(256, dtype=np.float32) - 127.5) * ratio + 144.0
    yy, xx = np.meshgrid(y, x, indexing="ij")
    prepared = np.empty((16, 256, 256), dtype=np.uint8)
    for zi, z_coordinate in enumerate(z):
        plane = scipy.ndimage.map_coordinates(
            source_crop, (np.full_like(yy, z_coordinate), yy, xx),
            order=1, mode="nearest", prefilter=False)
        prepared[zi] = np.rint(plane).clip(0, 255).astype(np.uint8)

    decoded_sha = hashlib.sha256(prepared.tobytes(order="C")).hexdigest()
    if decoded_sha != EXPECTED_ARRAY_SHA256:
        raise ValueError(f"prepared decoded array hash mismatch: {decoded_sha}")
    output_dir.mkdir(parents=True, exist_ok=False)
    input_path = output_dir / "control_field_input.npy"
    np.save(input_path, prepared, allow_pickle=False)
    file_sha = sha256(input_path)
    if file_sha != EXPECTED_NPY_SHA256:
        input_path.unlink()
        raise ValueError(f"prepared NPY file hash mismatch: {file_sha}")
    metadata = {
        "physical_scroll": "PHerc0139", "source_array": "0",
        "source_plane_selection_global_z": [3, 24], "source_crop_yx": list(crop_yx),
        "source_shape_zyx": list(array.shape), "source_spacing_um": list(spacing),
        "prepared_shape_zyx": [16, 256, 256], "prepared_spacing_um": [9.6, 9.6, 9.6],
        "recipe": "float32 SciPy map_coordinates order=1, mode=nearest, prefilter=false; np.rint, clip uint8",
        "decoded_array_sha256": decoded_sha, "npy_file_sha256": file_sha,
        "source_zarr_attrs_sha256": sha256(attrs_path),
        "source_array_metadata_sha256": sha256(source_path / "0" / ".zarray"),
    }
    receipt = {
        "schema": "argus-hecate-retained-control-preparation-v2",
        "state": "PREPARED_RETAINED_EXPOSED_CONTROL",
        "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "physical_scroll": "PHerc0139", "acquisition_id": CONTROL_ID,
        "acquisition_id_kind": "local exposed-control alias; source metadata has no official acquisition identifier",
        "source": {"path": str(source_path), **metadata},
        "input": {"path": str(input_path), "sha256": file_sha, "array_sha256": decoded_sha,
                  "shape_zyx": [16, 256, 256], "dtype": "uint8", "spacing_um": [9.6, 9.6, 9.6]},
        "limits": {"inference": False, "training": False, "target_search": False},
        "claim_ceiling": "retained exposed PHerc0139 control preparation only; no accuracy or reading claim",
    }
    (output_dir / "PREPARATION.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zarr", type=Path, required=True, help="local verified PHerc0139 title source Zarr")
    parser.add_argument("--output-dir", type=Path, required=True, help="new output directory; existing contents are never overwritten")
    args = parser.parse_args()
    print(json.dumps(prepare(args.source_zarr, args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
