A rendered Zarr records the effective surface geometry and renderer settings that produced it. When pyramid creation is disabled, its metadata now declares only the level that is created.

## What changed

- Add versioned `render_provenance`: renderer revision, effective geometry hash, source/group, affine, crop, orientation, slice/accumulation settings, output type, and effective surface interpolation.
- Sanitize URL credentials, queries and fragments before persisting remote locators.
- Preserve upstream's physical voxel units and effective linear/smooth interpolation settings.
- Correct `--pyramid false` in both ordinary rendering and `--pre`: `.zattrs` previously advertised levels 0–5 although only level 0 existed. It now advertises level 0. Default pyramid output still advertises and creates all six levels.

The writer correction prevents newly generated inconsistent stores. Existing malformed stores still need repair or the reader-side handling proposed in #1804. Credit #1831 for physical-unit handling and #1905 for band prefetch; those upstream changes are retained.

## Current local verification

Prepared head: `d7524301f` (full commit and file hashes in the local evidence packet). Based on current-main integration through `1f6f87b984b502ad992af2b6f10b0f07896aea4a`.

- Offline Ubuntu Release build, using existing dependencies and two build jobs: passed.
- Three focused C++ targets (`test_zarr`, `test_zarr_helpers`, `test_voxel_size_metadata`): passed, including preservation of level-0 axes/scales when higher levels are omitted.
- Actual renderer fetch/provenance suite: nine tests passed. The new regression covers enabled/disabled pyramids in both ordinary and `--pre` modes. Both disabled-pyramid subcases failed against the preserved pre-fix binary and pass after the correction.
- The immediately preceding integration passed all three upstream band-prefetch tests; the metadata-only follow-up does not change prefetch or pixel sampling.
- Retained PHercParis4 2.4 micrometer replay: all 12,288 pixels in a 3x64x64 crop match the prior candidate exactly. Decoded array SHA256: `da3bbe2971d8233eb43b0645ae5a783078902ad6af4135cab39add08796360d7`. Physical scale and axes remain identical; declared datasets change from 0–5 to 0.
- Minimum available system RAM during correction verification: 11.705 GiB; maximum GPU temperature52C; all owned workers exited. This is local verification; hosted CI on a future pushed head remains to run.

Earlier metadata-only PHerc0009B and retained Paris4 evidence remains preserved. The geometry hash identifies the actual float grid and grid scale after renderer sentinel handling and requested in-process flattening; it does not replace publishing the mesh. Local changes do not reconstruct provenance for previously published outputs or establish new ink.

## Reproduce the focused tests

Build the renderer and focused test targets with `VC_TESTING=ON`, then run:

```text
ctest --test-dir <build> --output-on-failure -R '^(test_zarr|test_zarr_helpers|test_voxel_size_metadata)$'
python volume-cartographer/core/test/test_render_fetch_failure.py <build>/bin/vc_render_tifxyz
python volume-cartographer/core/test/test_render_band_prefetch.py <build>/bin/vc_render_tifxyz
```

The CLI fixtures generate local synthetic data and use a loopback HTTP server. The retained real-data comparison is a separate, small local control; its evidence is not yet attached publicly. LLM tools assisted with implementation and testing under operator direction.

- [ ] Operator has reviewed this updated source, example and evidence before publication.
