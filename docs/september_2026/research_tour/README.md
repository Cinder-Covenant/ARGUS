# ARGUS: a five-minute operator and research tour

ARGUS helps an operator answer three practical questions: **which physical scroll is this, what evidence can this model legitimately provide, and did the tool produce the intended result?** It connects those answers to a bounded workflow, inspectable outputs and records of real failures and repairs.

Sections 1-5 use public source and retained September evidence at **[`1699f9c99c907cd678e92bb8994ec26db6809bcd`](https://github.com/Cinder-Covenant/ARGUS/tree/1699f9c99c907cd678e92bb8994ec26db6809bcd)**, with [successful portable CI](https://github.com/Cinder-Covenant/ARGUS/actions/runs/36801062911). Those four lightweight commands were rechecked from that revision. Section 6 adds the subsequently published PHerc0268 starter in this release. They read metadata or plan a run; they do not download CT, acquire weights or perform inference. The numerical and browser results are retained executions, not new runs performed for this tour.

## 1. Establish identity and exposure — 60 seconds

From the public ARGUS source root with Python 3.11, run:

```powershell
py -3.11 -B -m argus identify https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHerc0139/segments/20250108000004-w029_2025010827/surface-volumes/2.399um-0.22m-78keV-volume-20260102150214.zarr --no-route

py -3.11 -B -m argus exposure validate docs/exposure_example/EXAMPLE_RECORD.json

py -3.11 -B -m argus exposure check docs/exposure_example/EXAMPLE_RECORD.json --model ink_9um --scroll PHerc0139
```

The URL resolves to **PHerc0139**, volume `20260102150214`, at **MEDIUM** confidence from its declared URL and official survey. This does not inspect CT pixels. The exposure example validates **12 graph nodes, 19 claims and 9 edges**; nine nodes represent released entries and the others are ancestors. For `ink_9um` on PHerc0139, the expected result is **`NOT_ELIGIBLE`**: direct-label exposure is verified, and the other three channels have only inferred absence. That result explains why this is a known-data control.

The useful output is an inspectable source-qualified account of direct labels, teacher labels, pseudo-label lineage and raw-CT pretraining. Unknown exposure is not clean exposure. See the [exposure guide](https://github.com/Cinder-Covenant/ARGUS/blob/1699f9c99c907cd678e92bb8994ec26db6809bcd/docs/EXPOSURE_ACCOUNTING.md), [worked report](https://github.com/Cinder-Covenant/ARGUS/blob/1699f9c99c907cd678e92bb8994ec26db6809bcd/docs/exposure_example/EXAMPLE_REPORT.md) and [ancestry graph](https://github.com/Cinder-Covenant/ARGUS/blob/1699f9c99c907cd678e92bb8994ec26db6809bcd/docs/exposure_example/evidence_graph.svg). It records documented exposure; it does not measure leakage or prove model independence.

## 2. Inspect the bounded workflow — 40 seconds

```powershell
py -3.11 -B -m argus run pherc0139-w016-ink9um-control --dry-run
```

The plan covers identification, source and label acquisition, checkpoint verification, preparation, inference, scoring and a receipt. Its CT/label acquisition plan has **35 objects and a 62,504,960-byte upper bound**. The checkpoint is a separate prerequisite. This dry run reports **zero requests and no writes**; it honestly reports missing Villa runtime or checkpoint cache in the current shell. A real run requires those prerequisites and a single-use authorization. See [public run instructions](https://github.com/Cinder-Covenant/ARGUS/blob/1699f9c99c907cd678e92bb8994ec26db6809bcd/docs/PUBLIC_RUN.md).

## 3. Review known-data control A: the scored pipeline — 40 seconds

The retained **PHerc0139 w016 / released Villa `ink_9um`** workflow completed 11 stages. The [scoring receipt](https://github.com/Cinder-Covenant/ARGUS/blob/1699f9c99c907cd678e92bb8994ec26db6809bcd/docs/september_2026/evidence/evidence/PHERC0139_CONTROL_SCORE.json) records **AUC 0.772238 and AP 0.578875 on 90,367 validation pixels**. These scores demonstrate that this documented control pipeline moves data through preparation, inference and evaluation. The detector and data remain credited to their original authors; this is not a claim of improved accuracy or an independent physical-scroll test.

## 4. Review known-data control B: paired Hecate output — 60 seconds

This is a **different PHerc0139 title crop**, prepared at **9.6 micrometers** for Hecate, not the same array, acquisition or model as control A. The retained Workbench job `job_cd87c2d28995` completed and displayed its 2D output and selectable 3D depth slices. The new output hashes exactly matched the prior pinned control output. Its worker exited.

Inspect the [Hecate route and preparation runbook](https://github.com/Cinder-Covenant/ARGUS/blob/1699f9c99c907cd678e92bb8994ec26db6809bcd/docs/september_2026/HECATE_CONTROL_ROUTE_20260930.md) and [sanitized execution verification](https://github.com/Cinder-Covenant/ARGUS/blob/1699f9c99c907cd678e92bb8994ec26db6809bcd/docs/september_2026/hecate/ARGUS_CONTROL_EXECUTION_20260930.json). The later source check matched every pixel in the selected **21 x 288 x 288** source crop, and a separate strict-load receipt confirms the pinned model loads. Neither check reran inference.

Browser coverage is retained: any supplied 2D/depth captures are **stills**, not a fresh execution video. The stored demo service may report its earlier application build; its identity must remain visible if inspected. Software/output parity on an exposed control does not establish an unread-scroll reading or ink accuracy.

## 5. See the engineering outcomes — 60 seconds

| Actual problem | Demonstrated change | Inspect |
|---|---|---|
| An observed FP16 numerical failure could leave misleading output. | Non-finite inference is refused explicitly; checkpoint/input-form checks explain the mismatch. | [Failure receipt](https://github.com/Cinder-Covenant/ARGUS/blob/1699f9c99c907cd678e92bb8994ec26db6809bcd/docs/september_2026/evidence/evidence/INFERENCE_FAILURE.json), [Villa #1897](https://github.com/ScrollPrize/villa/pull/1897). |
| A disabled pyramid still advertised nonexistent levels. | Metadata describes only the written level; **12,288/12,288 tested pixels stay unchanged**. | [Correction receipt](https://github.com/Cinder-Covenant/ARGUS/blob/1699f9c99c907cd678e92bb8994ec26db6809bcd/docs/september_2026/evidence/evidence/RENDERER_CORRECTION.json), [Villa #1901](https://github.com/ScrollPrize/villa/pull/1901). |
| Producing Hecate's 2D and 3D outputs repeated the feature-network work. | Shared features preserve exact outputs in three actual-CLI pairs; median complete-process time falls **17.8357 to 11.5913 seconds, 35.01%**, on the pause-free 256-square control. | [Measurement and conditions](https://github.com/Cinder-Covenant/ARGUS/blob/1699f9c99c907cd678e92bb8994ec26db6809bcd/docs/september_2026/hecate/PUBLIC_MEASURED_RESULT_20260930.json), [comparison chart](https://github.com/Cinder-Covenant/ARGUS/blob/1699f9c99c907cd678e92bb8994ec26db6809bcd/docs/september_2026/hecate/ACTUAL_CLI_COMPARISON_20260930.png), [Hecate PR #1](https://huggingface.co/scrollprize/hecate/discussions/1). |
| A runtime could borrow completed steps from a neighboring process. | The displayed route now follows the selected runtime's own progress. | [Retained before/after UI captures](https://github.com/Cinder-Covenant/ARGUS/blob/1699f9c99c907cd678e92bb8994ec26db6809bcd/docs/september_2026/evidence/README.md). |

The larger Hecate timing comparison is thermally confounded; it does not replace the pause-free 35.01% result. Open upstream PRs are reviewable contributions, not assumed maintainer acceptance. The [supporting-control appendix](https://github.com/Cinder-Covenant/ARGUS/blob/1699f9c99c907cd678e92bb8994ec26db6809bcd/docs/september_2026/SUPPORTING_CONTROLS_20260930.md) also records a real label-refinement invocation and preservation of 8,098,000 valid known-title mask pixels, with their quality limits.

## 6. Find the research resources — 40 seconds

The [research collection](https://github.com/Cinder-Covenant/ARGUS/blob/1699f9c99c907cd678e92bb8994ec26db6809bcd/docs/september_2026/RESEARCH_COLLECTION_20260930.md) describes selected multi-scroll CT fields, four retained representation-learning baselines, a **1,505-point PHerc1203 profile atlas**, geometry comparisons and controlled failure checks. The [geometry diagnostic](https://github.com/Cinder-Covenant/ARGUS/blob/1699f9c99c907cd678e92bb8994ec26db6809bcd/docs/september_2026/geometry/README.md) and [corrected research supplement](https://github.com/Cinder-Covenant/ARGUS/blob/1699f9c99c907cd678e92bb8994ec26db6809bcd/docs/september_2026/RETAINED_RESEARCH_LIMITATIONS_20260930.md) expose mixed results and unresolved confounds rather than promoting them as an accuracy breakthrough.

| Resource | Availability |
|---|---|
| ARGUS software, exposure example, recipes and sanitized control/engineering records | Public at the linked revision. |
| PHerc0268 native-coarse starter: 342-entry manifest, deterministic 24-entry selection, reconstruction and local-loading scripts | [Public source-access kit](../../../artifacts/pherc0268_starter/README.md), with metadata/hash receipts and synthetic tests. No pixels or model weights are bundled. |
| Full selected CT and four model-weight payloads | Retained locally; roughly **22.43 GB** combined. No public download is claimed. |
| Selected 151-item source/result/card review packet | Prepared privately, roughly **1.25 MB**; must be supplied separately if wanted. It contains no raw CT, weights or target imagery. Its identity is recorded in the research collection. |

The PHerc0268 starter is separate from both PHerc0139 controls. From the ARGUS source root, inspect its default 24-field plan without fetching or decoding CT:

```sh
python -B artifacts/pherc0268_starter/reconstruct.py
```

The plan lists 192 source chunks, 50,331,648 uncompressed output bytes and 402,653,184 uncompressed source-chunk bytes. Actual compressed transfer bytes remain unknown. The [starter README](../../../artifacts/pherc0268_starter/README.md) explains source terms, explicit opt-in, local loading and the synthetic verification. Real-source reconstruction was not executed for this release. The kit does not validate the decoded original chunk collection or turn representation models into qualified ink detectors.


Team Cinder Covenant: Ryan Gurganious and Daine Ball. Credit Vesuvius Challenge data, Villa, released ink_9um, Hecate and the upstream representation architectures. Public CT reuse follows its original [Vesuvius open-data terms](https://scrollprize.org/data). ARGUS source is Apache-2.0; upstream patch and dataset licenses retain their own terms. For the complete submission, use the [September index](https://github.com/Cinder-Covenant/ARGUS/blob/main/docs/september_2026/README.md).
