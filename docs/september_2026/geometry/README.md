# PHerc0139 w016 evaluation-mask geometry diagnostic

This is a read-only diagnostic of the existing, exposed PHerc0139 control prediction and its exact validation region. It was pre-registered locally before the new analysis, then replayed with the public script against identical input hashes. It is **not** a new model, detector run, ink-accuracy improvement or unread-scroll reading.

## Finding

The original validation score is ROC AUC **0.772238** and average precision **0.578875** on 90,367 pixels, 22,765 positive, with no validation/supervision overlap. A score using only distance to the *validation-mask boundary* achieves AUC **0.689422**. This mask-only statistic sees no CT or prediction. It shows that the annotated evaluation geometry carries label information and is a necessary control for interpreting the model score.

In five distance bands frozen before analysis, the model's pair-weighted within-band AUC is **0.745823** across 88,941 evaluated pixels. The closest band, 1,426 pixels, was refused under the predeclared 2,000-pixel minimum; its 54 positives were not silently dropped from the global metric. A 199-draw within-64-pixel-block label-shuffle null has median AUC **0.642573** and 2.5–97.5% interval **0.640355–0.645406**; the observed model score exceeds all draws (Monte Carlo upper-tail p = 0.005, the resolution floor at 199 draws). A 512-draw spatial-block bootstrap gives AUC 2.5–97.5% interval **0.651840–0.869105**. There were 33 occupied blocks, so this uncertainty is broad.

These numbers indicate that the original association is not explained solely by this one mask-distance statistic or coarse 64-pixel block prevalence. They do **not** isolate CT-specific ink signal, eliminate other spatial confounds, establish transfer to another scroll or validate a reading. AUC values are separate diagnostics, not additive components.

## Exact evidence and reproduction

- [Frozen method](METHOD_FROZEN_BEFORE_RUN.json), SHA-256 `90887d0836807be48c46309c25ced1692d7439418bb0d2aba6cccca58b33f040`.
- The original [registered input hash set](REFERENCE_INPUTS.json), [v1 source](pherc0139_geometry_diagnostic.py) and [v1 preflight/result](PREFLIGHT.json, RESULT.json) are preserved as historical records. V1 pins the whole `PIPELINE_RUN_RECEIPT.json`, including machine-specific paths and timestamps, so it cannot replay a newly generated receipt.
- The [v2 scientific-input reference](REFERENCE_INPUTS_V2.json) pins the prediction and every accessed label-array metadata/chunk byte. It separately checks the receipt's PHerc0139/w016 identity, physical crop and sampling, label plane/score, checkpoint and exposure class. A receipt's raw SHA, run id, times and software revision are recorded as provenance, while paths and times do not participate in scientific identity. The [v2 replay source](pherc0139_geometry_diagnostic_v2.py) and [guard verification script](verify_pherc0139_geometry_diagnostic_v2.py) preserve this distinction.
- The v2 guard verification was run against the registered arrays: preflight used the retained root, then analysis used a relocated copy with changed run id, timestamps and path fields. All listed scientific fields matched the preserved [registered result](RESULT.json). The verification script also checks that changed prediction bytes, wrong scroll/crop/exposure, or source/reference changes between preflight and analysis are refused; run it to generate a fresh replay receipt locally.
- The independent scikit-learn scoring implementation reused the same retained prediction and label arrays; it is an independent calculation, not an independent data reproduction. No independent community use or third-party reproduction has been observed. This release therefore demonstrates a local replay, not adoption by another researcher.

Use a fresh output directory and an exact retained PHerc0139 w016 root containing `prediction.tif`, a pipeline receipt for that same control and the `labels/ink`, `labels/supervision`, `labels/validation` Zarr metadata/chunks. V2 permits relocated/new receipt provenance only when its stable scroll, crop, score and exposure contract matches and every prediction/label byte matches `REFERENCE_INPUTS_V2.json`. The source refuses changed arrays and changes between preflight and analysis. These files are not bundled in this package: the [control reproduction instructions](../evidence/REPRODUCE.md) explain how the original control inputs were obtained, but a user must obtain or retain those exact input bytes to run this diagnostic. Re-running inference is not part of the diagnostic.

The recorded source receipt identifies the label bucket but says it declares no separate licence. The package contains input hashes and derived statistics, not label arrays. Do not infer label redistribution rights from the CT-data licence; check the source's current terms before acquiring or using labels.

```text
python pherc0139_geometry_diagnostic_v2.py preflight --root /path/to/retained --output-dir /new/output
python pherc0139_geometry_diagnostic_v2.py analyze --root /path/to/retained --output-dir /new/output
python verify_pherc0139_geometry_diagnostic_v2.py --root /path/to/retained
```

The `input_root` in the frozen method records the original Windows location; v2 accepts another path when the pinned scientific bytes and stable receipt contract match. Preflight refuses an existing output directory, and analysis refuses a changed source, method, scientific input or stable receipt contract. This diagnostic runs on CPU and does not request a GPU, checkpoint weights or fresh detector inference. Its NumPy/numcodecs/Pillow/SciPy/scikit-learn dependencies must be installed in the chosen Python environment.
