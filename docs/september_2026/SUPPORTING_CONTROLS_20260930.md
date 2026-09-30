# Supporting September controls and integration evidence

These checks were completed on retained known-domain material. They support repeatability and diagnose limitations; none establishes new letters or improved unread-scroll detection.

## Larger PHerc0139 title output and mask preservation

The retained native-resolution PHerc0139 title control produced a `1780×5360` prediction. A replay using its declared support mask preserved **all 8,098,000 valid pixels exactly** relative to the unmasked replay (mean and maximum absolute difference zero inside the valid mask). The remaining 1,442,800 pixels were outside that mask; the masked output makes them zero. The masked TIFF SHA-256 is `7f74ed4529184b457811be540aa04975dbe52b40f98319f70901a5c0e7a9b7d0`; the local comparison receipt SHA-256 is `e87f3bacbb5155ea62e0f324607692b1b643aa4ab30f64cb906c5e32c683e5ba`.

This establishes that applying the mask did not alter predictions in the valid region. There are no pixel-aligned human ink labels for this title replay, so it is **not** an accuracy measurement. The cached `pherc0139_title_gt/villa_ink_ds8.jpg` reference is an upstream prediction image, not human ground truth. The exact earlier cached prediction configuration is incompletely recorded and is not used as a truth target here. No source CT array or title prediction image is redistributed in this supplement.

## Real label-refinement invocation

The ARGUS Villa adapter originally passed `--dilation-distance`, `--ridge-threshold` and `--num-workers`; the installed `vesuvius.refine_labels` CLI accepts the corresponding underscore flags. Correcting the argument names let the real CLI finish on one retained PHerc0841 w00 binary-label crop, shape `65×512×512`, in **43.127 seconds** including startup. It was CPU only. This is an invocation repair and real-data execution receipt, not a new annotation-quality result.

The output grew from 159,163 to 804,459 foreground voxels. Only 20.26% of the output lay inside the human supervision mask, versus 100% of the input. The tool never reads the paired CT; the later CT-intensity comparison was an external check. Its larger mask is not independently verified as correct, and the capability remains callable without scientific promotion.

## Hardware and scope

| Measured operation | Input and scope | Timing | Observed resource evidence |
| --- | --- | ---: | --- |
| Hecate actual-CLI baseline/candidate, three pairs | One exposed `16×256×256` PHerc0139 field; both 2D and 3D outputs | Median 17.8357 / 11.5913 s; 35.01% lower candidate time | GTX 1660 Ti 6 GiB, FP32, batch 1, two CPU threads; maximum 68°C, minimum 13.926 GiB available RAM and 4003 MiB whole-GPU free, peak process-tree RSS 1.541 GiB. No cooling pause. |
| Hecate larger actual-CLI baseline/candidate, three pairs | One exposed `16×512×512` PHerc0139 field; both 2D and 3D outputs | Median 163.010 / 57.328 s; observed 64.83% lower candidate process time under thermal guard | FP32, batch 1, stride 32, two CPU threads; 450 / 225 feature-network calls; maximum 70°C with unequal cooling pauses, minimum 13.198 GiB RAM available and 3786 MiB whole-GPU free, peak process-tree RSS 1.578 GiB. |
| Public ARGUS browser control, one run | Same retained exposed field, pinned Hecate, paired output | 6.523 s model inference within the complete governed job | Monitored minimum 13.734 GiB available RAM and 3.891 GiB whole-GPU free; maximum 63°C. The GPU process exited; 2D/3D output hashes match the earlier private control. This inference-only time is **not** compared with complete CLI process times. |
| PHerc0139 native title mask replay | Existing `1780×5360` known-title output | No new run timed in this supplement | 8,098,000 valid pixels preserved exactly; no aligned human title labels. |
| Villa label refinement | Retained `65×512×512` PHerc0841 w00 label crop | 43.127 s complete invocation | CPU only; output quality unqualified. |

The [larger actual-CLI machine-readable result](hecate/ACTUAL_CLI_512_RESULT_20260930.json) records all six process times, exact hashes and resource extrema. We independently decoded all six outputs after the run: each pair has identical 262,144 2D pixels and 4,194,304 3D voxels. The 512-square process-time result has a **material thermal confound**: the baseline runs paused for 55.2, 99.1 and 99.2 seconds, while the candidate runs paused for about 22 seconds each. Its 64.83% observed difference is not an isolated compute-speed estimate. The directly demonstrated efficiency mechanism is half as many feature-network calls for identical output.

PyTorch allocator observations are distinct from whole-GPU free memory, and model-forward/inference time is distinct from complete process time. These Hecate runs exclude raw CT preparation and UI transport. Fresh processes can still benefit from an OS file cache. The earlier 256-square, pause-free 35.01% result remains a separate controlled measurement; neither result forecasts whole-scroll throughput.

The upstream Hecate architecture, checkpoint and baseline CLI, the Villa tools, and the Vesuvius data belong to their respective authors. The work here concerns the ARGUS integration, measured software parity and the specific upstream patches linked from the [September index](README.md).
