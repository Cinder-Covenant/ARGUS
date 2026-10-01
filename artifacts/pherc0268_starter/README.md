# PHerc0268 self-supervised CT starter recipe

This small package makes an existing material-content corpus accessible through exact crop coordinates and portable code. It contains **342 original-source crop records**, SHA256 receipts for retained compressed files and a **24-field starter index (eight per anchor)**. It includes **no CT pixels, model weights or ink/fiber labels**. Code is MIT; source data has separate terms described in [source_terms.md](source_terms.md).

All 342 fields are 128³ uint8 crops of native isotropic 8.640 µm raw CT from PHerc0268. They were selected from 375 candidates around three dense-material anchors using a nonzero-fraction >=0.5 gate. Retained counts are g16=119, seed1=112 and seed2=111. Curation does not establish ink truth. The CT acquisition is upstream Vesuvius Challenge work; our contribution is selection/preparation, provenance and this access recipe.

The coordinate frame is native source **ZYX voxel indices**, with exclusive stop bounds. Filenames contain centers; origin is `max(center−64,0)`. Crops are not generally source-chunk aligned. Every filename center/grid/anchor and bounding box is checked by the offline parser. All fields had their nine retained files (one `.zarray` plus eight compressed chunks) present and hashed. Total retained bytes including metadata are 715,349,145; compressed chunk bytes alone are 715,225,341. No retained pixels were decoded by this addition.

## Quick offline use

Run from this directory, with Python 3.11 or newer:

```sh
python -B reconstruct.py
python -B -m unittest -v test_starter
```

The first command uses only the standard library, prints a dry-run access plan and makes no directory, network request or array read. The second creates synthetic Zarr fixtures in temporary directories beside the tests and removes them afterwards. It needs NumPy/Zarr/numcodecs. These tests also work under pytest:

```sh
python -B -m pytest -q -p no:cacheprovider test_starter.py
```

Validated existing runtimes: Python 3.11.9 with NumPy 2.4.6 / Zarr 2.18.7 / numcodecs 0.15.1, and the public ARGUS runtime with Zarr 3.1.6. Local output format remains Zarr v2 on both versions. [verification_receipt.json](verification_receipt.json) records exact versions and checks. No installation was performed for this addition. For a separate research environment, `requirements-local.txt` describes local-loader dependencies; `requirements-source-fetch.txt` adds S3 access libraries. The tested version pairs are recorded rather than claiming every permitted combination has been tested.

## Original-host reconstruction — explicit opt-in only

Default starter plan: 24 fields, 192 unique source chunks, 50,331,648 uncompressed output bytes and 402,653,184 unique-source-chunk uncompressed bytes. Source compression/network bytes are unknown. The code caps selected field count, the conservative **no-cache planned chunk-byte estimate** and planned chunk requests before making any request. Transport retries/metadata are not included; this is not a network byte meter. No cache is promised.

Review applicable [source terms](source_terms.md) first. A future researcher can explicitly fetch the bounded starter from its original public host with:

```sh
python -B reconstruct.py --allow-source-fetch --acknowledge-source-terms --output ./NEW_PH0268_DATA
```

`NEW_PH0268_DATA` must not exist; its parent must already exist. Overwrite/resume, traversal and parent link/junction indirection are refused. Both opt-in flags are required. Remote shape, chunks and dtype must match before writing. Only the declared crop slices are requested. Socket timeouts are set. Failures can leave partial output; it is not a complete dataset until `local_manifest.json` is written and validated. Never publish reconstructed pixels merely because fetching succeeded: exact redistribution applicability is unresolved.

**The command above was not run against real data by this addition.** The remote layout is supported by the retained original fetch/helper source, while reconstruction was tested against an independent synthetic mock source. This distinction remains part of the release evidence.

Planning all 342 crops requires explicit larger caps; this command still makes no requests:

```sh
python -B reconstruct.py --all --max-fields 342 --max-source-uncompressed-bytes 6000000000 --max-source-chunk-requests 2736
```

That plan has 1,532 unique source chunks (3,212,836,864 uncompressed bytes), up to 2,736 planned chunk reads without cache (5,737,807,872 uncompressed bytes), and 717,225,984 output voxel bytes. These are estimates from boxes/chunk geometry, not observed download amounts.

Reconstruction writes a new `local_manifest.json` with hashes of its own encoded files. Codec bytes can differ from the archived corpus even for identical decoded values; use the matching local manifest for the reconstructed directory. This package does not falsely compare different encodings as byte-identical content.

## Local loading

Without `--decode`, inspection reads JSON and file sizes only. Hash verification streams compressed bytes without decoding. There is no automatic first-field fallback:

```sh
python -B load_local.py --manifest ./NEW_PH0268_DATA/local_manifest.json --root ./NEW_PH0268_DATA --entry seed1_000000_z7013_y6373_x4166.zarr --verify-hashes
```

Use an exact name actually present in your selected manifest; this example is included in the default 24. To decode an explicit deterministic 64³ training view, add `--decode --offset Z Y X`, with offsets 0..64. `--normalize` applies per-crop float32 z-score normalization; constant crops become zero. Returned coordinates preserve the same source ZYX frame. Actual decoding was exercised only on synthetic fixtures in this addition.

## Provenance and validation limits

`pherc0268_manifest.json` records the actual SHA256 of the retained original crop-fetch source and volume helper, plus the repository HEAD at audit. That HEAD is not proof of the training-time source revision. `sampler_24.json` binds to the full manifest SHA256 and records its deterministic selection rule: sorted retained basenames per anchor, indices `floor(j*(N−1)/7)`, j=0..7. No image or model output chose the sampler.

Tests cover hand-calculated native coordinates and axis-specific synthetic voxels, crop bounds and normalization, malformed coordinate/source/count refusal, missing chunks, hash corruption, path escape/fresh output, source-chunk estimates, offline default, opt-in/cap refusal before network, and mocked source reconstruction followed by loading its generated receipt. They establish code behavior, not validity of unread target content, source-host availability, model performance or scientific adoption. Preparation performed no training, inference, checkpoint loading, target visualization, reading claim or Google-form submission. No target CT pixels or model weights are included for upload.
