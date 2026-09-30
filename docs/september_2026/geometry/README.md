# PHerc0139 w016 evaluation-mask geometry diagnostic

This is a read-only diagnostic of the existing, exposed PHerc0139 control prediction and its exact validation region. It was pre-registered locally before the new analysis, then replayed with the public script against identical input hashes. It is **not** a new model, detector run, ink-accuracy improvement or unread-scroll reading.

## Finding

The original validation score is ROC AUC **0.772238** and average precision **0.578875** on 90,367 pixels, 22,765 positive, with no validation/supervision overlap. A score using only distance to the *validation-mask boundary* achieves AUC **0.689422**. This mask-only statistic sees no CT or prediction. It shows that the annotated evaluation geometry carries label information and is a necessary control for interpreting the model score.

In five distance bands frozen before analysis, the model's pair-weighted within-band AUC is **0.745823** across 88,941 evaluated pixels. The closest band, 1,426 pixels, was refused under the predeclared 2,000-pixel minimum; its 54 positives were not silently dropped from the global metric. A 199-draw within-64-pixel-block label-shuffle null has median AUC **0.642573** and 2.5–97.5% interval **0.640355–0.645406**; the observed model score exceeds all draws (Monte Carlo upper-tail p = 0.005, the resolution floor at 199 draws). A 512-draw spatial-block bootstrap gives AUC 2.5–97.5% interval **0.651840–0.869105**. There were 33 occupied blocks, so this uncertainty is broad.

These numbers indicate that the original association is not explained solely by this one mask-distance statistic or coarse 64-pixel block prevalence. They do **not** isolate CT-specific ink signal, eliminate other spatial confounds, establish transfer to another scroll or validate a reading. AUC values are separate diagnostics, not additive components.

## Exact evidence and reproduction

- [Frozen method](METHOD_FROZEN_BEFORE_RUN.json), SHA-256 `90887d0836807be48c46309c25ced1692d7439418bb0d2aba6cccca58b33f040`.
- [Registered input hash set](REFERENCE_INPUTS.json) and [portable replay source](pherc0139_geometry_diagnostic.py), source SHA-256 `b2e41dfbb9dc1e948a6b077d32e55f6fbeecfbba2e873354e1d6a9b12f0defb0`.
- [Replay preflight](PREFLIGHT.json) and [complete numeric result](RESULT.json). The portable replay's entire scientific result matched the preserved frozen local run after excluding timestamp and source/receipt identity fields. An independent scikit-learn implementation reproduced the global and every scored-band ROC AUC.

Use a fresh output directory and an exact retained PHerc0139 w016 root containing `prediction.tif`, `PIPELINE_RUN_RECEIPT.json` and the `labels/ink`, `labels/supervision`, `labels/validation` Zarr metadata/chunks. The source checks every accessed input hash against `REFERENCE_INPUTS.json` and refuses a mismatch. The [control reproduction instructions](../evidence/REPRODUCE.md) describe how those public inputs were originally obtained.

```text
python pherc0139_geometry_diagnostic.py preflight --root /path/to/retained --output-dir /new/output
python pherc0139_geometry_diagnostic.py analyze --root /path/to/retained --output-dir /new/output
```

The `input_root` in the frozen method records the original Windows location; the replay's `--root` can point elsewhere with identical bytes. Preflight refuses an existing output directory, and analysis refuses a changed source, method or input hash set. This diagnostic runs on CPU and does not request a GPU, checkpoint, network access or fresh detector inference.
