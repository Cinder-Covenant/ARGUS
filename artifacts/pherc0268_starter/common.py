"""PHerc0268 provenance and bounded-access helpers. No network or array imports."""
import hashlib
import itertools
import json
import re
from pathlib import Path

SOURCE_URI = "s3://vesuvius-challenge-open-data/PHerc0268/volumes/20251110183117-8.640um-1.2m-116keV-masked.zarr"
SOURCE_SHAPE = [14833, 12145, 12145]
ANCHORS_XYZ = {"seed1": [4566, 6773, 7413], "seed2": [2271, 7852, 3702], "g16": [6701, 2903, 10571]}
OFFSETS = [-400, -200, 0, 200, 400]
NAME = re.compile(r"(g16|seed1|seed2)_(\d{2})(\d{2})(\d{2})_z(\d+)_y(\d+)_x(\d+)\.zarr")


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def coordinates(name):
    match = NAME.fullmatch(name)
    if not match:
        raise ValueError("invalid field basename")
    anchor, *numbers = match.groups()
    iz, iy, ix, z, y, x = map(int, numbers)
    if any(i not in range(5) for i in [iz, iy, ix]):
        raise ValueError("grid index outside 0..4")
    ax, ay, az = ANCHORS_XYZ[anchor]
    expected = [az + OFFSETS[iz], ay + OFFSETS[iy], ax + OFFSETS[ix]]
    if [z, y, x] != expected:
        raise ValueError("filename center disagrees with anchor/grid recipe")
    origin = [max(c - 64, 0) for c in expected]
    stop = [c + 128 for c in origin]
    if any(e > n for e, n in zip(stop, SOURCE_SHAPE)):
        raise ValueError("crop exceeds source volume")
    return {"anchor": anchor, "grid_index_zyx": [iz, iy, ix], "center_zyx": expected,
            "origin_zyx": origin, "stop_zyx_exclusive": stop}


def read_manifest(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema") != "pherc0268-starter-manifest-v1":
        raise ValueError("unsupported manifest schema")
    source = value.get("source", {})
    if source.get("uri") != SOURCE_URI or source.get("level") != 0 or source.get("axes") != "ZYX":
        raise ValueError("source identity/axes mismatch")
    if source.get("shape_zyx") != SOURCE_SHAPE or source.get("chunks_zyx") != [128] * 3:
        raise ValueError("source shape/chunks mismatch")
    entries = value.get("entries", [])
    names = set()
    for entry in entries:
        name = entry["name"]
        if name in names:
            raise ValueError("duplicate field")
        names.add(name)
        expected = coordinates(name)
        if any(entry.get(key) != data for key, data in expected.items()):
            raise ValueError("coordinate provenance mismatch")
        if entry.get("shape_zyx") != [128] * 3 or entry.get("dtype") != "uint8":
            raise ValueError("field shape/dtype mismatch")
        if entry.get("chunks_zyx") != [64] * 3:
            raise ValueError("field chunk shape mismatch")
        files = entry.get("files", [])
        required = {".zarray"} | {".".join(map(str, c)) for c in itertools.product(range(2), repeat=3)}
        found = set()
        for item in files:
            filename = item["path"]
            if filename not in required | {".zattrs"} or filename in found:
                raise ValueError("invalid/duplicate field file")
            found.add(filename)
            if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) or item["bytes"] < 0:
                raise ValueError("invalid file receipt")
        if not required.issubset(found):
            raise ValueError("missing declared chunks/metadata")
    if value.get("retained_field_count") != len(entries):
        raise ValueError("field count mismatch")
    return value


def select_entries(manifest, selection=None):
    by_name = {e["name"]: e for e in manifest["entries"]}
    if selection is None:
        return list(by_name.values())
    value = json.loads(Path(selection).read_text(encoding="utf-8"))
    if value.get("schema") != "pherc0268-selection-v1":
        raise ValueError("unsupported selection schema")
    names = value["names"]
    if value.get("count") != len(names):
        raise ValueError("selection count mismatch")
    if len(names) != len(set(names)) or any(n not in by_name for n in names):
        raise ValueError("duplicate or unknown selected field")
    return [by_name[n] for n in names]


def access_plan(entries):
    chunks = set()
    for entry in entries:
        spans = [range(a // 128, (b - 1) // 128 + 1)
                 for a, b in zip(entry["origin_zyx"], entry["stop_zyx_exclusive"])]
        chunks.update(itertools.product(*spans))
    return {"fields": len(entries), "output_uncompressed_bytes": len(entries) * 128 ** 3,
            "unique_source_chunks": len(chunks),
            "source_chunk_uncompressed_bytes": len(chunks) * 128 ** 3,
            "network_compressed_bytes": "unknown; codec compression and repeat requests vary",
            "source_chunk_requests_without_cache_upper_bound": len(entries) * 8,
            "source_chunk_uncompressed_bytes_without_cache_upper_bound": len(entries) * 8 * 128 ** 3,
            "source_uri": SOURCE_URI, "level": 0, "axes": "ZYX"}


def child_path(root, name):
    root = Path(root).resolve(strict=True)
    path = root / name
    if Path(name).name != name or path.is_symlink() or path.resolve().parent != root:
        raise ValueError("field path escapes root or follows a link")
    return path


def fresh_output(path):
    candidate = Path(path).expanduser()
    if ".." in candidate.parts:
        raise ValueError("output must not contain parent traversal")
    candidate = candidate.absolute()
    if candidate.exists() or candidate.is_symlink():
        raise ValueError("output must be a new directory; overwrite/resume is refused")
    parent = candidate.parent
    if not parent.is_dir() or parent.resolve() != parent:
        raise ValueError("output parent must already exist without link/junction indirection")
    if candidate == Path(candidate.anchor) or candidate == Path.home():
        raise ValueError("unsafe output root")
    return candidate
