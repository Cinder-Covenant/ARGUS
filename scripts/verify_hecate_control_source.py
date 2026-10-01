"""Compare only the PHerc0139 title-control chunks used by the Hecate crop."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import time
import urllib.request
from pathlib import Path

import numpy as np
import zarr

SOURCE_URL = (
    "https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/"
    "PHerc0139/segments/20260422000000-title_2026042222_zmid_flatboi/"
    "surface-volumes/9.362um-1.2m-113keV-volume-20250728140407.zarr/"
)
ZATTRS_SHA256 = "dffc62c435f2782cc6f40e0325f33f31de71e1a70609d97994509f4ddfbc40bf"
ZARRAY_SHA256 = "e9bc19dcbeb7a11cff1748c242d4c7a79a77d0538a8e09cd552f2a1ba6f73440"
LIMIT_BYTES = 16 * 1024 * 1024
HEADER_TIMEOUT = 20


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def request(method: str, url: str, limit: int | None = None):
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=HEADER_TIMEOUT) as response:
        if method == "HEAD":
            return int(response.headers["Content-Length"]), response.headers.get("ETag")
        body = response.read((limit + 1) if limit is not None else -1)
        if limit is not None and len(body) > limit:
            raise ValueError("source response exceeded the preflight byte limit")
        return body


def verify(retained_zarr: Path, output_receipt: Path, maximum_bytes: int) -> dict:
    retained_zarr = retained_zarr.resolve()
    output_receipt = output_receipt.resolve()
    if output_receipt.exists():
        raise FileExistsError(f"refusing to overwrite source verification receipt: {output_receipt}")

    # Metadata is small. Verify its exact identity before deriving chunk keys.
    zattrs = request("GET", SOURCE_URL + ".zattrs")
    zarray_bytes = request("GET", SOURCE_URL + "0/.zarray")
    if sha256(zattrs) != ZATTRS_SHA256 or sha256(zarray_bytes) != ZARRAY_SHA256:
        raise ValueError("public source metadata identity differs from the pinned PHerc0139 source")
    attrs, metadata = json.loads(zattrs), json.loads(zarray_bytes)
    if (metadata.get("shape") != [28, 1780, 5360] or
            metadata.get("chunks") != [28, 128, 128] or
            metadata.get("dimension_separator") != "/" or
            metadata.get("compressor") is not None or metadata.get("dtype") != "|u1"):
        raise ValueError("PHerc0139 source array layout differs from the expected ZYX uint8 control")

    retained = zarr.open(str(retained_zarr), mode="r")
    retained_array = retained["0"] if hasattr(retained, "keys") and "0" in retained else retained
    if tuple(retained_array.shape) == (28, 1780, 5360):
        retained_z_start = 3
    elif tuple(retained_array.shape) == (21, 1780, 5360):
        # Existing extracted source contains global planes [3:24) at local z=0.
        retained_z_start = 0
    else:
        raise ValueError(f"retained source has an unexpected PHerc0139 shape: {tuple(retained_array.shape)}")
    if retained_array.dtype != np.dtype("uint8"):
        raise ValueError("retained PHerc0139 source must be uint8")

    # Crop y[880:1168], x[2608:2896] intersects 4 by 4 whole-Z source chunks.
    y0, y1, x0, x1 = 880, 1168, 2608, 2896
    y_indices = range(y0 // 128, (y1 - 1) // 128 + 1)
    x_indices = range(x0 // 128, (x1 - 1) // 128 + 1)
    keys = [f"0/0/{yi}/{xi}" for yi in y_indices for xi in x_indices]

    def head(key: str):
        length, etag = request("HEAD", SOURCE_URL + key)
        return key, length, etag

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        headers = list(pool.map(head, keys))
    total = sum(length for _, length, _ in headers)
    if total > maximum_bytes or total > LIMIT_BYTES:
        raise ValueError(f"required source chunks total {total} bytes, above the admitted limit {min(maximum_bytes, LIMIT_BYTES)}")
    expected_chunk_bytes = 28 * 128 * 128
    if any(length != expected_chunk_bytes for _, length, _ in headers):
        raise ValueError("a required full-Z source chunk has an unexpected byte length")

    assembled = np.empty((21, y1 - y0, x1 - x0), dtype=np.uint8)
    remote_chunk_hashes = {}
    for key, length, _ in headers:
        payload = request("GET", SOURCE_URL + key, limit=length)
        if len(payload) != length:
            raise ValueError(f"short source chunk: {key}")
        remote_chunk_hashes[key] = sha256(payload)
        yi, xi = (int(part) for part in key.split("/")[2:])
        gy0, gx0 = yi * 128, xi * 128
        cy0, cy1 = max(y0, gy0), min(y1, gy0 + 128)
        cx0, cx1 = max(x0, gx0), min(x1, gx0 + 128)
        tile = np.frombuffer(payload, dtype=np.uint8).reshape(28, 128, 128)
        local = tile[3:24, cy0-gy0:cy1-gy0, cx0-gx0:cx1-gx0]
        retained_view = np.asarray(
            retained_array[retained_z_start:retained_z_start + 21,
                           cy0:cy1, cx0:cx1], dtype=np.uint8)
        if not np.array_equal(local, retained_view):
            raise ValueError(f"public chunk differs from retained source at {key}")
        assembled[:, cy0-y0:cy1-y0, cx0-x0:cx1-x0] = local

    receipt = {
        "schema": "argus-hecate-public-source-correspondence-v1",
        "state": "EXACT_REQUIRED_SOURCE_PIXELS_MATCHED",
        "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "physical_scroll": "PHerc0139",
        "source_url": SOURCE_URL,
        "source_zattrs_sha256": sha256(zattrs),
        "source_zarray_sha256": sha256(zarray_bytes),
        "source_z_selection": [3, 24],
        "source_yx_crop": [y0, y1, x0, x1],
        "source_shape_zyx": [28, 1780, 5360],
        "matched_pixels": int(assembled.size),
        "matched_array_sha256": sha256(assembled.tobytes(order="C")),
        "required_chunk_count": len(headers),
        "required_chunk_bytes": total,
        "max_bytes_admitted": min(maximum_bytes, LIMIT_BYTES),
        "required_chunk_sha256": remote_chunk_hashes,
        "retained_zarr_root": str(retained_zarr),
        "retained_zarr_shape_zyx": list(retained_array.shape),
        "retained_local_z_start": retained_z_start,
        "claim_ceiling": "exact equality for the 21x288x288 retained control crop; not whole-volume validation",
    }
    output_receipt.parent.mkdir(parents=True, exist_ok=True)
    with output_receipt.open("x", encoding="utf-8") as target:
        json.dump(receipt, target, indent=2)
        target.write("\n")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retained-zarr", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--max-bytes", type=int, default=LIMIT_BYTES)
    args = parser.parse_args()
    result = verify(args.retained_zarr, args.receipt, args.max_bytes)
    print(json.dumps({k: v for k, v in result.items() if k != "required_chunk_sha256"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
