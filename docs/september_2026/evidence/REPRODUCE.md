# Reproduce the evidence

## 1. Inspect code without inference

ARGUS public baseline: `44886642107bf82506126595551e96d4fb44efa9`. Villa candidate `d7524301f7efe0fbf5a7e761b75fab498f68d5d3` incorporates tested upstream base `1f6f87b984b502ad992af2b6f10b0f07896aea4a`. At packaging time live main was `3a4754ffc0478f6c888b6e45c3711872298dd5b1`; its only later changed file was `lasagna/tifxyz_format.md` (a scale-documentation correction). The executable source did not change in that comparison. The hashes and test outcomes refer to the tested identities; no new build is implied by the remote refresh.

In a suitable ARGUS checkout of the public baseline:

```text
git apply --check <package>/patches/ARGUS_RUNTIME_ISOLATION.patch
git apply <package>/patches/ARGUS_RUNTIME_ISOLATION.patch
python -m pytest -q <package>/reproduction/test_runtime_isolation.py
```

The three functions are extracted unchanged from already-existing local tests; only imports and the module description were made standalone. They mock both authorities and perform no network request or CT access.

In a Villa checkout at `1f6f87b984b502ad992af2b6f10b0f07896aea4a`, apply `patches/VILLA_1901_ON_CURRENT_MAIN.patch`. It contains provenance and pyramid corrections in five files. The smaller `PYRAMID_METADATA_FIX.patch` is the historical incremental patch against `d816158d257a4e2420321e0635ab8d98e2dacd22`; **do not apply both**.

Build with the project's documented dependencies and `VC_TESTING=ON`, then:

```text
ctest --test-dir <build> --output-on-failure -R '^(test_zarr|test_zarr_helpers|test_voxel_size_metadata)$'
python volume-cartographer/core/test/test_render_fetch_failure.py <build>/bin/vc_render_tifxyz
python volume-cartographer/core/test/test_render_band_prefetch.py <build>/bin/vc_render_tifxyz
```

The nine-test renderer and three-target C++ results in this package were completed on the candidate. The three band-prefetch tests passed on the immediately preceding integration; the metadata-only follow-up did not change that path. Do not call this full-suite or hosted validation of the local head.

## 2. Reproduce the PHerc0139 control

Use the public ARGUS [`docs/PUBLIC_RUN.md`](https://github.com/Cinder-Covenant/ARGUS/blob/44886642107bf82506126595551e96d4fb44efa9/docs/PUBLIC_RUN.md). The included target manifest is copied byte for byte from that public export. It identifies the exact surface-volume crop, label URLs and checkpoint revision/hash. This requires a native Villa/PyTorch GPU environment; the Docker UI alone has no GPU passthrough. Resource supervision and explicit run authorization are required.

After a run, or against the original retained output directory containing `labels/`, `prediction.tif` and `PIPELINE_RUN_RECEIPT.json`:

```text
python <package>/reproduction/verify_control_score.py --root <run-directory> --output <new-score-receipt.json>
```

Dependencies: NumPy, numcodecs and Pillow, already part of the recorded environment. The adapted verifier accepts explicit paths, refuses overwriting an output and requires no missing label chunks or overlap with supervision. Its histogram calculation is retained from the original independent verifier. The public label bucket is mutable: compare the recorded individual chunk hashes and prediction hash before interpreting reproduction differences. A fresh public-data run need not reproduce an old result if its underlying bytes changed.

Expected original control: 90,367 validation pixels; 22,765 positives; AUC 0.7722380370197259; AP 0.5788753796123365; prediction SHA256 `4e24125200a8ef8981566eb1f43568fc4b1a001ce30dd696c3c85b366e35288c`. No inference was repeated to assemble this package.

## 3. Limits of the real-data examples

PHerc1667 source crops and model weights are not bundled. Public regression fixtures and linked PR code reproduce the numerical/input behavior; the real-data excerpts and historical log hashes document the encountered failure. The differing 17/21-slice crops are not a controlled accuracy experiment.

Paris4 exact equality covers one 3x64x64 retained crop. The new before/after result establishes metadata correctness with unchanged pixels. Earlier same-candidate repeatability is a separate result. The small crop is not a reading-quality or whole-renderer qualification.

## Packaging correction

The original saved runtime patch had CRLF line endings. The included LF transport patch applies to the exact public baseline module and reproduces the tested module bytes. See `evidence/RUNTIME_PATCH_TRANSPORT_ERRATUM.json`; it supersedes the historical patch-file hash only.
