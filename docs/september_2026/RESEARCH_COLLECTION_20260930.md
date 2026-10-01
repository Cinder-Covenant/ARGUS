# ARGUS retained research collection

**Metadata-only summary, prepared September 30, 2026.** This page catalogs a selected research collection and the records retained for technical review. It is not a downloadable CT or model release. The ARGUS control, reproducibility, and engineering evidence is linked from the [September evidence index](README.md).

## Retained corpus inventory

A file-manifest audit lists 4,399 candidate field containers. **4,398 have all expected chunk filenames present; one partial container is quarantined.** The complete-by-filename counts cover six physical scrolls:

| Selection | Complete containers | Field shape | Source and use |
| --- | ---: | ---: | --- |
| PHerc1203 high-resolution | 832 | 256 x 256 x 256 | 2.403 micrometer, 77 keV CT; selection assisted by external PHerc1203 registration work from Shuhan Yang, for self-supervised training and material-profile research. |
| PHerc0268 native coarse | 342 | 128 x 128 x 128 | 8.640 micrometer, 116 keV CT; deterministic sampling around material anchors for MAE and small DINO baselines. |
| Additional coarse collection | 3,224 | 128 x 128 x 128 | PHerc0800: 374; PHerc1447: 1,862 across three source entries; PHerc0139: 919; PHerc0009B: 69. |

The retained chunk inventory totals **18,301,672,008 compressed bytes**, including the quarantined partial container. Complete containers represent **21,437,087,744 logical voxel entries**. These are counts of selected containers, not unique physical volume, independent training examples, or validated chunks. Fields can overlap; PHerc1203 origin and overlap accounting remains incomplete. The CT bytes were not decoded in the inventory audit. PHerc1203 high-resolution material is described as training and structural research, not as low-resolution unread-scroll reading evidence. PHerc0009B raw CT was included in one coarse pretraining collection, so its later evaluation is not a physically unexposed-scroll test.

The source CT and registration resources retain their original authorship. The contribution claimed here is the selection, curation, extraction, training work, and analysis, with provenance and unresolved overlap disclosed.

## Selected trained baselines

Four locally retained training outputs total **4,125,955,140 bytes** (about 4.13 GB): a PHerc1203 MAE baseline, a PHerc0268 MAE baseline, a small PHerc0268 DINO/iBOT model, and a multiscroll coarse DINO prototype. Their upstream architectures and source data are credited. Configurations, training logs, evaluation records, and streamed checkpoint SHA-256 identities are cataloged in the prepared review packet.

These are representation-learning baselines, not a new qualified ink detector or accuracy breakthrough. Reported downstream results are modest or negative, and the multiscroll coarse model includes raw-PHerc0009B pretraining exposure. Checkpoint files were hash-identified but not loaded or run as part of the inventory audit.

## Derived research and quality-control records

- **PHerc1203 site-profile atlas:** 1,505 native-coordinate point records. The method assigns 1,148 ambiguous-blend, 228 single-sheet-resolved, 80 invalid-surface, and 49 unclassifiable outcomes. These are algorithm-derived local-profile classes, not human ink labels, dense pixel-to-CT maps, or certified sheets. A 50.48-degree normal-estimator error on one PHercParis4 control is disclosed.
- **Geometry cohort:** 21 processed surfaces across seven physical scrolls and 17 paired flatten comparisons, based on 23 frozen inputs. Its area totals describe input geometry, not newly unwrapped papyrus. Results are mixed and sensitive to an outlier; CT continuity has not been validated.
- **EXP7 controlled quality checks:** 204 synthetic positives, 24 topology defects, 48 real-reference configurations, and 88 planted real defects. These counts describe constructed checks and configurations, not independent physical surfaces.
- **Exposure, acquisition, and transfer analysis:** a public nine-model exposure example is available in [ARGUS exposure accounting](../EXPOSURE_ACCOUNTING.md). The broader retained records include eight model families/four exposure channels and 23 acquisition statistics plus a reference. Historical transfer summaries retain their scoring, preparation, source-binding, and aggregation limitations; see the [corrected archival supplement](RETAINED_RESEARCH_LIMITATIONS_20260930.md).

## What ARGUS adds

ARGUS connects physical-scroll identity, data/model exposure records, governed provider execution, evaluation, task-bound 3D inspection, coordinate/evidence lookup, selected annotation bridges, and storage/restore workflows. The public release demonstrates the specific control and engineering routes documented in the [Hecate runbook](HECATE_CONTROL_ROUTE_20260930.md), [supporting controls](SUPPORTING_CONTROLS_20260930.md), and [geometry diagnostic](geometry/README.md). Code present in the broader workbench is not described as an executed or independently validated route unless there is a corresponding receipt.

The submission's quantitative engineering evidence remains the primary demonstrated result: explicit refusal of the observed FP16 non-finite failure, corrected renderer metadata with unchanged tested pixels, and bitwise-equal paired Hecate outputs with a pause-free 35.01% lower median complete-process time on one small exposed PHerc0139 control. The larger 512-square timing remains thermally confounded.

## Availability and claim limits

The public ARGUS repository includes this summary and its linked software/evidence, but **does not include the 18.30 GB CT chunk collection or the four checkpoint payloads**. Their combined retained size is about 22.43 GB, and they remain at their original local storage paths; no public download route is claimed. A 1.25 MB private review packet contains 151 selected source/result/card entries and the detailed field/model inventories, but it is not publicly linked or included here. Its SHA-256 is 55d0a506eb8f810773ce495083e14fb418035c7597eefd5da5e51c181d79f93a; a separately supplied copy can be checked against that identity. The packet excludes raw CT payloads, target images, model weights, and the purpose-locked N1558 receipt.

This is a research-resource and engineering contribution. It does not report new training or inference in the inventory audit, an unread-scroll reading, improved ink accuracy, independent community adoption, or a prize outcome.
