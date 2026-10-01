# ARGUS retained research collection

**Released September 30, 2026.** The collection combines downloadable own trained baselines, actual computed geometry/profile resources, and a selection index over already-public community CT. Start with the [public resource index](PUBLIC_RESOURCES.md) for direct links and per-scroll reproduction status, or the [September evidence index](README.md) for ARGUS's executed controls and measured engineering results. Publication preserves the original research timeline, including August training; it does not describe those runs as new September training.

## Retained CT selections and public originals

The [public selection manifest](https://huggingface.co/datasets/darthceltic85/argus-research-resources/blob/b0b09fe4311e833b3ca530a1449c7195643362dc/ct/ct_selection_manifest.json) describes 4,399 candidate containers, of which **4,398 have every expected chunk filename**; one partial is quarantined and excluded. The six exact acquisitions are already public upstream. Their [source catalog](https://huggingface.co/datasets/darthceltic85/argus-research-resources/blob/b0b09fe4311e833b3ca530a1449c7195643362dc/ct/source_catalog.json) supplies original URLs, source shapes, scan identity and per-asset CC BY-NC 4.0 evidence.

| Physical scroll | Complete containers | Shape | Selection and origin status |
| --- | ---: | --- | --- |
| PHerc1203 | 832 | 256³ | 2.403 µm / 77 keV; selection assisted by external matched-point registration from Shuhan Yang. Exact per-field native origins remain unresolved and are null in the manifest. |
| PHerc0268 | 342 | 128³ | 8.640 µm / 116 keV; three-anchor material sampling, with exact native origins and exclusive stops. |
| PHerc0800 | 374 | 128³ | Native coarse fields; origins inferred from retained global chunk keys and assembly source. |
| PHerc1447 | 1,862 | 128³ | Three selection entries refer to one physical scroll/acquisition; origins inferred from global chunk keys. |
| PHerc0139 | 919 | 128³ | Native coarse selection, distinct from ARGUS's surface-relative PHerc0139 controls. |
| PHerc0009B | 69 | 128³ | Native coarse selection; this raw CT appears in multiscroll DINO pretraining. |

There are **3,566 coordinate-indexed fields**, with **30 exact duplicate declared source boxes**, leaving 3,536 distinct boxes by source/origin/stop identity. This does not establish decoded-byte equality, independence or total unique coverage. PHerc1203 origin/overlap accounting remains incomplete. Forty-three PHerc1447 edge containers extend beyond the source's declared Z length; their valid source extent is clipped in the manifest. Stored padding was not decoded or assumed to be zero.

The complete containers total **18,295,712,472 retained compressed chunk bytes** and **21,437,087,744 logical voxel entries**. Neither is a count of novel acquisition, independent examples or validated CT. Earlier inventory totals included the partial container; the public complete-only total corrects that distinction. The historical coarse assembly count of 3,278 is corrected to 3,224 actual additional containers because 54 PHerc0009B basenames collided. PHerc0268's 342 fields are counted once.

The original CT intensities are public; our local selected copies were private. This release provides original-host links and our selection/provenance additions instead of duplicating those pixels. It credits Vesuvius Challenge's acquisitions and external registration rather than claiming acquisition or registration authorship. PHerc1203's high-resolution material supports structural/self-supervised research, not low-resolution unread-scroll reading evidence. PHerc0009B evaluation is not a physically unexposed-scroll test.

## PHerc0268 source-access starter

The [PHerc0268 starter](../../artifacts/pherc0268_starter/README.md) gives exact coordinates and retained-file hashes for 342 fields, a deterministic 24-field selection, a local Zarr loader and bounded opt-in original-host reconstruction. Its default is a no-network dry run. The material-content gate is not ink/fiber supervision. Metadata, streamed stored-byte hashes and synthetic fixtures were checked; real-source reconstruction and target decoding were not performed for this release.

## Downloadable own trained baselines

The [model release](https://huggingface.co/darthceltic85/argus-research-baselines/tree/5b4e750bf1174185bd1d301d0f12df75689a1b7a) contains four original checkpoints totaling **4,125,955,140 bytes**, individual cards, sanitized configurations, source pins/notices and a metadata-only inspection helper. These are own training outputs using credited Villa/dinovol architectures and community CT, released under CC BY-NC 4.0.

| Checkpoint | Historical completed work | Retained result and limit |
| --- | --- | --- |
| [PHerc1203 MAE v4b](https://huggingface.co/darthceltic85/argus-research-baselines/blob/5b4e750bf1174185bd1d301d0f12df75689a1b7a/pherc1203-mae-v4b/README.md) | 13-epoch continuation/early stop of our earlier PHerc1203 model. | Best reported reconstruction loss 0.5455; not an ink metric. Earlier initialization lineage is incompletely reconstructed. |
| [PHerc0268 MAE epoch29](https://huggingface.co/darthceltic85/argus-research-baselines/blob/5b4e750bf1174185bd1d301d0f12df75689a1b7a/pherc0268-mae-epoch29/README.md) | Random-init 35-epoch run; epoch29 retained. | Reconstruction 0.7177 versus first epoch 0.9245. Full-population ink-residual AUC 0.5404; representation/domain mismatch limits transfer. |
| [PHerc0268 small DINO/iBOT step3000](https://huggingface.co/darthceltic85/argus-research-baselines/blob/5b4e750bf1174185bd1d301d0f12df75689a1b7a/pherc0268-dino-proof-step3000/README.md) | Completed 3,000-step proof configuration, continuing our step2000 output. | Six-segment/80-ROI grouped probe AUC 0.5641; field splits do not prove physical independence. |
| [Multiscroll coarse DINO/iBOT step3750](https://huggingface.co/darthceltic85/argus-research-baselines/blob/5b4e750bf1174185bd1d301d0f12df75689a1b7a/multiscroll-coarse-dino-step3750/README.md) | Retained step3750 of an interrupted run, not completion of a 9,000-step ceiling. | PHerc0009B prototype/linear AUC 0.457292/0.512292; raw-CT pretraining exposure is present. |

The publisher verified remote sizes and checkpoint SHA-256 identities against the local originals. Bounded archive/opcode inspection did not deserialize tensors. **No fresh strict load, forward pass, inference or training was performed on these four models.** Files include training state, and DINO archives retain historical machine paths. Source pins describe inspected code, not proven exact training-time environments. Cards explain loader expectations; slim backbone/safetensors exports and demonstrated current-runtime loading remain future work. Modest or negative probes are useful baselines, not qualified ink detectors or an accuracy breakthrough.

## Actual derived resources

The [geometry collection](https://huggingface.co/datasets/darthceltic85/argus-research-resources/blob/b0b09fe4311e833b3ca530a1449c7195643362dc/geometry/README.md) contains **248 files**, including computed arrays and meshes, their metadata, source, notices and frozen results:

- **PHerc1203 atlas:** two original 1,505-site native-coordinate tables, methods and scalar diagnostics. Automatic classes: 1,148 ambiguous-blend, 228 single-sheet-resolved, 80 invalid-surface and 49 unclassifiable. These are profile outputs, not human labels, dense pixel-to-CT mappings or certified sheets. One Paris4 normal-estimator error was 50.48 degrees.
- **Geometry cohort:** 63 NumPy fields (`angle_defect`, `cell_class`, `chart_labels`) over 21 surfaces/seven scrolls; 23 frozen inputs, 17 paired flatten comparisons and historical 21/21 deterministic replay receipts. Official input meshes are linked by URL/hash, not duplicated. Area is input geometry; mixed/outlier-sensitive results and unvalidated CT continuity preclude a robust usable-area improvement claim.
- **Generated geometry:** 13 TIFXYZ meshes and available generation tags from our seed/run outputs of the upstream Villa grower. One corrected U03 PHerc1203 82×82 mesh has a local geometric PASS (reported native area 2.0924 cm²); nine PHerc0268 fixtures are diagnostic; three PHerc0125/PHerc1451 fixtures retain explicit suspect/failure labels. Geometry PASS does not certify sheet continuity, ink or reading; overlapping areas must not be summed into new papyrus.
- **EXP7 and qualifier source:** protocols, harness/dependency snapshots and frozen records for 204 synthetic positives, 24 topology defects, 48 real-reference configurations and 88 planted defects. These are controlled cases/configurations, not independent surfaces. Four HIGH layouts failed solver/layout criteria; one real reference limits generalization. The proposed surface qualifier retains its prior failed sabotage check.
- **Coordinate and exposure records:** Paris4 coordinate/frame/support diagnostics and a historical eight-family/four-channel registry. The current [nine-model exposure example](../EXPOSURE_ACCOUNTING.md) remains the canonical software example. Unknown exposure is not demonstrated contamination or independence.

The collection includes array-header/index metadata and an example for reading derived arrays without running archived jobs. Archived scripts and receipts retain historical paths and private assumptions; they are source records, not a demonstrated complete fresh-machine pipeline. N1558 purpose-locked evidence, target images, raw CT and upstream registration archives are excluded. Existing [Herculaneum Scroll Tools](https://github.com/DarthCeltic/herculaneum-scroll-tools) CT-support surveys and source remain useful public resources and are linked rather than copied.

## Verification and demonstrated ARGUS routes

Both Hugging Face repositories are public. The release publisher matched all expected Git blob sizes or LFS SHA-256 identities, with anonymous access checks. Dataset revision `b0b09fe4311e833b3ca530a1449c7195643362dc` contains **254 files / 46,032,414 bytes**; model revision `5b4e750bf1174185bd1d301d0f12df75689a1b7a` contains 23 files, including the four checkpoints. Access and byte-identity checks do not establish scientific validity or fresh execution.

ARGUS's executed routes remain documented in the [public control](../PUBLIC_RUN.md), [Hecate runbook](HECATE_CONTROL_ROUTE_20260930.md), [supporting controls](SUPPORTING_CONTROLS_20260930.md) and [geometry diagnostic](geometry/README.md). Demonstrated engineering results are explicit refusal of observed non-finite FP16 output, corrected renderer metadata with unchanged tested pixels, and bitwise-equal paired Hecate outputs with a pause-free **35.01% lower median process time** on one small exposed PHerc0139 field. The larger timing is thermally confounded.

Historical transfer summaries keep their scoring, preparation, source-binding and aggregation limits in the [corrected archival supplement](RETAINED_RESEARCH_LIMITATIONS_20260930.md). Publishing these resources does not rerun those experiments, establish unread-scroll letters, improve ink accuracy, demonstrate adoption or predict a prize outcome. Original code, CT, mesh, architecture and registration authors retain credit and their applicable licenses.
