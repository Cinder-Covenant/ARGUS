# Public ARGUS research resources

This index separates what we obtained from where another researcher can obtain it and how reproduction was checked. Original CT comes from Vesuvius Challenge; our additions are the selection/provenance index, own trained baselines, computed analysis/geometry and ARGUS's integration and engineering work. Original dates and upstream authorship remain visible.

## Download our distinct releases

| Resource | Public files and use | Reproduction status |
| --- | --- | --- |
| [Four own trained baselines](https://huggingface.co/darthceltic85/argus-research-baselines/tree/5b4e750bf1174185bd1d301d0f12df75689a1b7a) | 4,125,955,140 checkpoint bytes, cards/configurations, source pins/licenses and a metadata-only inspection helper. Two MAE and two DINO/iBOT outputs for reconstruction/representation research. | Exact sizes/SHA-256 verified against originals; bounded archive inspection. No fresh load, forward pass or inference. Full training-state artifacts; see each card's loader/environment limits. |
| [CT selection index](https://huggingface.co/datasets/darthceltic85/argus-research-resources/blob/b0b09fe4311e833b3ca530a1449c7195643362dc/ct/README.md) | 4,398 complete-by-filename containers over six already-public acquisitions. Coordinates where known, source/array metadata and exact per-volume license evidence. | 3,566 known origins; 832 PHerc1203 origins unresolved. Thirty exact duplicate source boxes and 43 PHerc1447 edge containers disclosed. No new decoded-data equality check. |
| [Computed atlas/geometry/diagnostic collection](https://huggingface.co/datasets/darthceltic85/argus-research-resources/blob/b0b09fe4311e833b3ca530a1449c7195643362dc/geometry/README.md) | 248 files: 1,505-site PHerc1203 tables/methods; 63 arrays/21 surfaces; 13 generated XYZ meshes/tags; EXP7, qualifier and coordinate/exposure records. | Actual computed payloads, headers/indexes and historical replay/results. Geometry PASS and automatic classes are not certified sheet/ink truth. Archived jobs were not rerun. |
| [PHerc0268 small source-access kit](../../artifacts/pherc0268_starter/README.md) | Exact 342-field origin/hash manifest, deterministic 24-field selection, local loader and bounded opt-in original-host reconstruction. | Metadata and synthetic tests; dry run requires no CT access. No live-source reconstruction or target decode in publication preparation. |

The resource dataset is **254 files / 46,032,414 bytes** at revision `b0b09fe4311e833b3ca530a1449c7195643362dc`. The model release is 23 files at revision `5b4e750bf1174185bd1d301d0f12df75689a1b7a`. Both are public; expected Git blob sizes/LFS SHA-256 identities and anonymous access were checked. These checks establish availability and file identity, not scientific validation.

## Original CT: six-scroll source index

All six exact official volume entries identify **CC BY-NC 4.0**. The [source catalog](https://huggingface.co/datasets/darthceltic85/argus-research-resources/blob/b0b09fe4311e833b3ca530a1449c7195643362dc/ct/source_catalog.json) records anonymous metadata access, license pointers/hashes, shapes and original HTTPS/S3 roots. The links below are readable array metadata; remove `0/.zarray` to obtain the corresponding original Zarr group root for a client. Full CT intensities remain at that original public host.

| Scroll | Original acquisition: metadata link | What we retained / provide |
| --- | --- | --- |
| PHerc1203 | [20260319130212, 2.403 µm / 77 keV](https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHerc1203/volumes/20260319130212-2.403um-0.2m-77keV-masked.zarr/0/.zarray) | 832 high-resolution 256³ fields; MAE continuation; 1,505-site atlas; corrected U03 generated mesh. Per-field origins still require pinned external registration recovery. High-resolution structural research is not low-resolution unread-reading evidence. |
| PHerc0268 | [20251110183117, 8.640 µm / 116 keV](https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHerc0268/volumes/20251110183117-8.640um-1.2m-116keV-masked.zarr/0/.zarray) | 342 exact 128³ fields, 24-field access recipe, MAE and small DINO/iBOT, nine diagnostic generated meshes. Sampling gate measures nonzero material content, not ink/fiber labels. |
| PHerc0800 | [20250521135224, 8.640 µm / 116 keV](https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHerc0800/volumes/20250521135224-8.640um-1.2m-116keV-masked.zarr/0/.zarray) | 374 128³ fields, chunk-key coordinate index and participation in multiscroll coarse pretraining. |
| PHerc1447 | [20250521151220, 8.640 µm / 116 keV](https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHerc1447/volumes/20250521151220-8.640um-1.2m-116keV-masked.zarr/0/.zarray) | 1,862 128³ containers across three selections of one acquisition, chunk-key coordinates and disclosed source-edge validity. |
| PHerc0139 | [20250728140407, 9.362 µm / 113 keV](https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHerc0139/volumes/20250728140407-9.362um-1.2m-113keV-masked.zarr/0/.zarray) | 919 native coarse fields for pretraining. The executed ink_9um/Hecate controls use separately documented surface-relative acquisitions/preparation. |
| PHerc0009B | [20250521125136, 8.640 µm / 116 keV](https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHerc0009B/volumes/20250521125136-8.640um-1.2m-116keV-masked.zarr/0/.zarray) | 69 128³ fields. Raw CT pretraining exposure is present; later probe results are not unexposed-scroll generalization. |

## Model cards and direct checkpoint files

Use the cards before loading. The metadata-only helper verifies downloaded size/SHA-256 without `torch.load`, model construction or inference: from a downloaded matching repository tree, run `python -B inspect_checkpoint.py --root . --manifest MODEL_MANIFEST.json`. It does not download files automatically. The original artifacts include optimizer/training state; DINO files retain disclosed historical local paths. The release does not provide slim/safetensors exports or assert current-runtime compatibility.

| Baseline | Card | Exact original checkpoint |
| --- | --- | --- |
| PHerc1203 MAE v4b | [card](https://huggingface.co/darthceltic85/argus-research-baselines/blob/5b4e750bf1174185bd1d301d0f12df75689a1b7a/pherc1203-mae-v4b/README.md) | [502,669,047 bytes](https://huggingface.co/darthceltic85/argus-research-baselines/resolve/5b4e750bf1174185bd1d301d0f12df75689a1b7a/pherc1203-mae-v4b/pherc1203_mae_v4b_final.pth) |
| PHerc0268 MAE epoch29 | [card](https://huggingface.co/darthceltic85/argus-research-baselines/blob/5b4e750bf1174185bd1d301d0f12df75689a1b7a/pherc0268-mae-epoch29/README.md) | [502,668,637 bytes](https://huggingface.co/darthceltic85/argus-research-baselines/resolve/5b4e750bf1174185bd1d301d0f12df75689a1b7a/pherc0268-mae-epoch29/phc0268_mae_v1_epoch29.pth) |
| PHerc0268 DINO/iBOT step3000 | [card](https://huggingface.co/darthceltic85/argus-research-baselines/blob/5b4e750bf1174185bd1d301d0f12df75689a1b7a/pherc0268-dino-proof-step3000/README.md) | [1,560,125,368 bytes](https://huggingface.co/darthceltic85/argus-research-baselines/resolve/5b4e750bf1174185bd1d301d0f12df75689a1b7a/pherc0268-dino-proof-step3000/checkpoint_step_003000_v2.pt) |
| Multiscroll coarse DINO/iBOT step3750 | [card](https://huggingface.co/darthceltic85/argus-research-baselines/blob/5b4e750bf1174185bd1d301d0f12df75689a1b7a/multiscroll-coarse-dino-step3750/README.md) | [1,560,492,088 bytes](https://huggingface.co/darthceltic85/argus-research-baselines/resolve/5b4e750bf1174185bd1d301d0f12df75689a1b7a/multiscroll-coarse-dino-step3750/checkpoint_step_003750.pt) |

Reconstruction loss and the modest/negative retained probes are described in the [collection guide](RESEARCH_COLLECTION_20260930.md). None qualifies an ink detector. Own training outputs are dated historical work, including August 2026 runs; the September 30 event is this public release, not newly executed training.

## Existing public tools, system tags and executed routes

- [ARGUS exposure accounting](../EXPOSURE_ACCOUNTING.md), [nine released entries plus three ancestors](../exposure_example/EXAMPLE_RECORD.json), [worked report](../exposure_example/EXAMPLE_REPORT.md) and [graph](../exposure_example/evidence_graph.svg): 12 nodes, 19 claims, nine edges. Direct labels, teacher labels, pseudo-label lineage and raw-CT pretraining are tracked separately; unknown is not clean exposure or proven contamination. The older registry in the geometry package preserves its dated eight-family scope.
- [Official survey registry](../../argus/public_official_survey.json): metadata source for physical-scroll/volume identification, not proof from pixel inspection.
- [Herculaneum Scroll Tools](https://github.com/DarthCeltic/herculaneum-scroll-tools): already-public CT-support survey JSONs, halo metadata and registration/winding/dual-energy source. These are distinct from the 1,505-site profile atlas and are linked rather than republished here.
- [ARGUS public known-data control](../PUBLIC_RUN.md), [Hecate preparation and guarded route](HECATE_CONTROL_ROUTE_20260930.md), [supporting controls](SUPPORTING_CONTROLS_20260930.md), [scoring geometry diagnostic](geometry/README.md) and [five-minute tour](research_tour/README.md): executed control/engineering records, with their exact source revisions and limits.
- [Corrected archival supplement](RETAINED_RESEARCH_LIMITATIONS_20260930.md): historical transfer scoring, preparation/source-binding and topology limits. This resource release does not claim new rescoring or causal generalization.

## Credits and terms

Team Cinder Covenant: Ryan Gurganious and Daine Ball. Credit Vesuvius Challenge for the scans, Shuhan Yang for external PHerc1203 registration, Villa/dinovol/Hecate and original mesh/annotation/architecture authors. Cite exact scan IDs, checkpoint hashes and release revisions. Automatic material/profile classes and per-vertex generation tags are useful derived fields with their stated semantics; they are not human ink/fiber ground truth.

Original six-volume CT terms are [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) as recorded per asset; maintain noncommercial use, attribution and modification notices. See the [official data guide](https://scrollprize.org/data). The CT index does not duplicate pixels or override separately applicable registered-server agreements. Own released weights use CC BY-NC 4.0. ARGUS code is Apache-2.0; archived Vesuvius and Villa code retains MIT notices and dinovol's applicable MIT/Meta Apache-2.0 notices. Code licenses do not license upstream CT/mesh/annotation data. No confirmed unread-scroll text, ink-accuracy gain, independent adoption or prize outcome is claimed.
