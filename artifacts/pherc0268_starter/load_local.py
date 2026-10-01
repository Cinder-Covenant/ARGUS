"""Local PHerc0268 loader. Inspection is default; --decode is explicit."""
import argparse
import json
from pathlib import Path
from common import child_path, read_manifest, sha256


def inspect_field(root, entry, verify_hashes=False):
    path = child_path(root, entry["name"])
    if not path.is_dir():
        raise ValueError("field directory absent")
    for item in entry["files"]:
        file = child_path(path, item["path"])
        if not file.is_file() or file.stat().st_size != item["bytes"]:
            raise ValueError("missing file or byte count mismatch")
        if verify_hashes and sha256(file) != item["sha256"]:
            raise ValueError("file SHA256 mismatch")
    meta = json.loads((path / ".zarray").read_text(encoding="utf-8"))
    if meta.get("shape") != [128] * 3 or meta.get("chunks") != [64] * 3 or meta.get("dtype") != "|u1":
        raise ValueError("stored metadata disagrees with manifest")
    if meta.get("zarr_format") != 2 or meta.get("order") != "C":
        raise ValueError("unsupported stored array format/order")
    return path


def load_crop(root, entry, offset=(0, 0, 0), normalize=False, verify_hashes=True):
    if len(offset) != 3 or any(not isinstance(o, int) or o < 0 or o + 64 > 128 for o in offset):
        raise ValueError("64-cube offset must be three integers in 0..64, in ZYX order")
    path = inspect_field(root, entry, verify_hashes=verify_hashes)
    import numpy as np
    import zarr
    array = zarr.open_array(str(path), mode="r")
    result = np.asarray(array[tuple(slice(o, o + 64) for o in offset)])
    if result.shape != (64, 64, 64) or result.dtype != np.uint8:
        raise ValueError("decoded crop shape/dtype mismatch")
    if normalize:
        result = result.astype(np.float32)
        sigma = float(result.std())
        result = (result - float(result.mean())) / sigma if sigma > 0 else np.zeros_like(result)
    return result, {"origin_zyx": [a + b for a, b in zip(entry["origin_zyx"], offset)],
                    "stop_zyx_exclusive": [a + b + 64 for a, b in zip(entry["origin_zyx"], offset)],
                    "spacing_um_zyx": [8.640] * 3, "axes": "ZYX", "normalized": normalize}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--entry", required=True, help="exact .zarr basename from manifest")
    p.add_argument("--verify-hashes", action="store_true")
    p.add_argument("--decode", action="store_true", help="explicitly read retained pixels")
    p.add_argument("--offset", nargs=3, type=int, default=[0, 0, 0], metavar=("Z", "Y", "X"))
    p.add_argument("--normalize", action="store_true")
    a = p.parse_args(argv)
    entries = {e["name"]: e for e in read_manifest(a.manifest)["entries"]}
    if a.entry not in entries:
        p.error("unknown entry; no fallback selection")
    entry = entries[a.entry]
    try:
        inspect_field(a.root, entry, a.verify_hashes)
        result = {"entry": a.entry, "status": "metadata inspected; no pixels decoded"}
        if a.decode:
            array, coordinates = load_crop(a.root, entry, tuple(a.offset), a.normalize)
            result.update(status="explicitly decoded crop", shape=list(array.shape), dtype=str(array.dtype), coordinates=coordinates)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError) as exc:
        p.error(str(exc))


if __name__ == "__main__":
    main()
