"""Dry-run first, bounded original-host crop recipe. No rehosting permission implied."""
import argparse
import json
from pathlib import Path
from common import SOURCE_URI, SOURCE_SHAPE, access_plan, fresh_output, read_manifest, select_entries, sha256


def open_remote():
    import fsspec
    import zarr
    options = {"anon": True, "config_kwargs": {"connect_timeout": 10, "read_timeout": 30}}
    if int(zarr.__version__.split(".")[0]) >= 3:
        mapper = zarr.storage.FsspecStore.from_url(SOURCE_URI, storage_options=options, read_only=True)
    else:
        mapper = fsspec.get_mapper(SOURCE_URI, **options)
    return zarr.open_group(store=mapper, mode="r")["0"]


def execute(entries, manifest, output):
    # Called only after two explicit flags, caps and fresh-output preflight.
    import numpy as np
    import zarr
    source = open_remote()
    if list(source.shape) != SOURCE_SHAPE or list(source.chunks) != [128] * 3 or source.dtype != np.uint8:
        raise ValueError("remote source shape/chunks/dtype differs; refused")
    output.mkdir(exist_ok=False)
    receipt = dict(manifest)
    receipt["entries"] = []
    receipt["retained_field_count"] = len(entries)
    receipt["payload_status"] = "reconstructed from original host; codec bytes can differ from archived fields"
    for entry in entries:
        slices = tuple(slice(a, b) for a, b in zip(entry["origin_zyx"], entry["stop_zyx_exclusive"]))
        block = np.asarray(source[slices])
        if block.shape != (128, 128, 128) or block.dtype != np.uint8:
            raise ValueError("source returned incompatible field")
        field = output / entry["name"]
        kwargs = ({"config": {"write_empty_chunks": True}, "zarr_format": 2}
                  if int(zarr.__version__.split(".")[0]) >= 3
                  else {"write_empty_chunks": True, "zarr_version": 2})
        arr = zarr.open_array(str(field), mode="w", shape=block.shape, chunks=(64,) * 3,
                              dtype="uint8", order="C", **kwargs)
        arr[:] = block
        local = dict(entry)
        local["files"] = [{"path": p.name, "bytes": p.stat().st_size, "sha256": sha256(p)}
                          for p in sorted(field.iterdir()) if p.is_file()]
        receipt["entries"].append(local)
        print(json.dumps({"written": entry["name"]}), flush=True)
    (output / "local_manifest.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, default=Path(__file__).with_name("pherc0268_manifest.json"))
    p.add_argument("--selection", type=Path, default=Path(__file__).with_name("sampler_24.json"))
    p.add_argument("--all", action="store_true", help="plan all retained fields; explicit caps still apply")
    p.add_argument("--allow-source-fetch", action="store_true")
    p.add_argument("--acknowledge-source-terms", action="store_true", help="you have reviewed applicable original-host terms; does not grant redistribution")
    p.add_argument("--output", type=Path)
    p.add_argument("--max-fields", type=int, default=24)
    p.add_argument("--max-source-uncompressed-bytes", type=int, default=512 * 1024 ** 2)
    p.add_argument("--max-source-chunk-requests", type=int, default=192,
                   help="cap planned chunk reads before transport-level retries; not a transfer meter")
    a = p.parse_args(argv)
    try:
        manifest = read_manifest(a.manifest)
        if not a.all:
            selection = json.loads(a.selection.read_text(encoding="utf-8"))
            if selection.get("manifest_sha256") != sha256(a.manifest):
                raise ValueError("selection was made against a different manifest SHA256")
        entries = select_entries(manifest, None if a.all else a.selection)
        plan = access_plan(entries)
        plan["dry_run"] = not a.allow_source_fetch
        if a.max_fields < 1 or a.max_source_uncompressed_bytes < 1 or a.max_source_chunk_requests < 1 or not entries:
            raise ValueError("positive caps and a nonempty selection are required")
        if len(entries) > a.max_fields or plan["source_chunk_uncompressed_bytes_without_cache_upper_bound"] > a.max_source_uncompressed_bytes:
            raise ValueError("planned access exceeds explicit field/byte cap")
        if plan["source_chunk_requests_without_cache_upper_bound"] > a.max_source_chunk_requests:
            raise ValueError("planned access exceeds explicit chunk-request cap")
        plan["source_fetch_validation"] = "not run by this package's authors; remote layout inferred from original retained fetch source"
        print(json.dumps(plan, indent=2))
        if not a.allow_source_fetch:
            return
        if not a.acknowledge_source_terms or a.output is None:
            raise ValueError("fetch requires --acknowledge-source-terms and --output NEW_DIRECTORY")
        output = fresh_output(a.output)
        execute(entries, manifest, output)
    except (ValueError, OSError, KeyError) as exc:
        p.error(str(exc))


if __name__ == "__main__":
    main()
