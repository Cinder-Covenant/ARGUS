"""Inventory retained filenames/JSON and hash archived bytes; never decode pixels."""
import argparse
import collections
import json
from pathlib import Path
from common import ANCHORS_XYZ, SOURCE_URI, SOURCE_SHAPE, coordinates, read_manifest, sha256


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--original-fetch-source", type=Path, required=True)
    p.add_argument("--original-volume-helper", type=Path, required=True)
    a = p.parse_args()
    destination = Path(__file__).resolve().parent
    entries = []
    for directory in sorted(a.root.glob("*.zarr")):
        if directory.is_symlink() or directory.resolve().parent != a.root.resolve():
            raise ValueError("retained directory follows a link")
        meta = json.loads((directory / ".zarray").read_text(encoding="utf-8"))
        if meta.get("shape") != [128] * 3 or meta.get("chunks") != [64] * 3 or meta.get("dtype") != "|u1":
            raise ValueError("unexpected retained metadata")
        entry = {"name": directory.name, **coordinates(directory.name), "shape_zyx": [128] * 3,
                 "chunks_zyx": [64] * 3, "dtype": "uint8", "files": []}
        for file in sorted(directory.iterdir()):
            if not file.is_file() or file.is_symlink() or file.resolve().parent != directory.resolve():
                raise ValueError("unexpected nested/nonregular file")
            entry["files"].append({"path": file.name, "bytes": file.stat().st_size, "sha256": sha256(file)})
        entries.append(entry)
    if len(entries) != 342:
        raise ValueError("retained field count changed; expected 342")
    manifest = {"schema": "pherc0268-starter-manifest-v1", "retained_field_count": len(entries),
                "source": {"uri": SOURCE_URI, "level": 0, "axes": "ZYX", "shape_zyx": SOURCE_SHAPE,
                           "chunks_zyx": [128] * 3, "spacing_um_zyx": [8.640] * 3},
                "recipe": {"anchors_xyz": ANCHORS_XYZ, "grid_offsets_native_voxels": [-400, -200, 0, 200, 400],
                           "candidate_count": 375, "nonzero_fraction_gate": 0.5,
                           "per_field_density_not_retained": True,
                           "origin_rule": "max(center_zyx - 64, 0); stop=origin+128; not generally chunk-aligned"},
                "provenance": {"original_fetch_source_sha256": sha256(a.original_fetch_source),
                               "original_volume_helper_sha256": sha256(a.original_volume_helper),
                               "local_repository_head_at_audit": "07bd96a1a465511c778af9107ec396323e5ed222",
                               "head_is_not_proof_of_training_time_revision": True},
                "payload_status": "archived byte hashes and JSON only; no pixels bundled or decoded in this audit",
                "terms_status": "Exact official PHerc0268 volume metadata declares CC BY-NC 4.0; original-host recipe only; see source_terms.md",
                "entries": entries}
    path = destination / "pherc0268_manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    read_manifest(path)
    names = []
    for anchor in sorted(ANCHORS_XYZ):
        group = sorted(e["name"] for e in entries if e["anchor"] == anchor)
        if len(group) < 8:
            raise ValueError("anchor has fewer than eight retained fields")
        names.extend(group[j * (len(group) - 1) // 7] for j in range(8))
    selection = {"schema": "pherc0268-selection-v1", "count": 24,
                 "rule": "per anchor: lexicographically sorted retained basenames; indices floor(j*(N-1)/7), j=0..7",
                 "manifest_sha256": sha256(path), "names": names}
    (destination / "sampler_24.json").write_text(json.dumps(selection, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"fields": len(entries), "anchors": dict(collections.Counter(e["anchor"] for e in entries)),
                      "sampler": len(names), "archived_bytes": sum(f["bytes"] for e in entries for f in e["files"]),
                      "manifest_sha256": sha256(path)}, indent=2))


if __name__ == "__main__":
    main()
