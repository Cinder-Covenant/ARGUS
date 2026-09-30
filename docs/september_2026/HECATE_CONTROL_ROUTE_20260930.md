# Retained PHerc0139 Hecate control through ARGUS

This is an exposed apparatus control. It checks the real Hecate 9.6 µm reader, governed job, paired 2D/3D writer and identity-bound Workbench display. It does not measure ink accuracy or demonstrate a reading on an unread scroll.

## Configure the retained input

The public source contains the execution route, but does not redistribute CT, the prepared input, the model weights or the strict-load runtime receipt. Set these environment variables on the local ARGUS services before starting them:

| Variable | Expected material |
| --- | --- |
| `ARGUS_REPO` | This ARGUS checkout; new control receipts go under its `artifacts/` directory. |
| `ARGUS_HOME` | One isolated runtime state directory. |
| `ARGUS_HECATE_CONTROL_INPUT` | Retained `uint8` ZYX `.npy` control field, shape `16×256×256`. |
| `ARGUS_HECATE_CONTROL_PREPARATION` | Adjacent preparation JSON binding PHerc0139 and the exact input SHA-256. |
| `ARGUS_HECATE_RUNTIME` | Existing Python environment with the pinned Hecate dependencies and CUDA. |
| `ARGUS_HECATE_PROVIDER` | `hecate.py` at upstream revision `9cb86e500e944b11a06a7020403cde5dffb5bcb2`; its Git blob must be `a2d3494361d81107d4bd9268cfe377d80f22cd0a`. |
| `ARGUS_HECATE_RUNTIME_RECEIPT` | Existing Hecate strict-load receipt with `STRICT_LOAD_PASSED`. |

The checkpoint `hecate_9.6um.pth` must sit next to the provider source and hash to `809f4f10f7cb7afa19b4bee0f7d2ab31edd7e11b664f9f210cc9c17f22fcfe5d`. The retained input used in the September demonstration hashes to `3bdfab85fed733757ed3a0021f6240e02afb9bda9af9a12a7ef67c5ae156eb86`. The control is unavailable when required material is missing; a different input or scroll cannot pass its execution binding.

Open Workbench with PHerc0139 selected, choose **Hecate output**, open a governed session, review the exact control plan and approve it. The job shows tile progress; on completion, the viewer loads the 2D image and 3D depth slices from the new receipt. Each job receives a fresh output directory. Cancellation and resource failures retain their partial evidence without presenting it as a completed control.

## Physical preparation recipe and limit

The retained surface-volume input was built from the PHerc0139 title positive-control surface at native 9.362 µm, using original Z planes `[3:24)` from the public 28-plane volume. The public [source metadata](https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHerc0139/segments/20260422000000-title_2026042222_zmid_flatboi/surface-volumes/9.362um-1.2m-113keV-volume-20250728140407.zarr/.zattrs) identifies the source; the retained local chunks were hashed before preparation. The 256 field uses source crop `z[0:21), y[880:1168), x[2608:2896)`. Its output-grid coordinates are

```text
ratio = 9.6 / 9.362
z = (arange(16) - 7.5) * ratio + 10
y = (arange(256) - 127.5) * ratio + 1024
x = (arange(256) - 127.5) * ratio + 2752
```

Subtract the crop origin for local coordinates. Sample with SciPy `map_coordinates(order=1, mode="nearest", prefilter=False)` on a float32 crop, then `rint`, clip to `[0,255]` and cast to `uint8`. The expected decoded array SHA-256 is `b7d2f762e67031302eb55420851c4236e5d11696ff26639d1915bcdc94208ca6`.

This documents the retained recipe and permits a hash check. The remote source chunk bytes were not independently compared with the retained local chunks in this release, so a fresh-machine public-source reconstruction is not claimed.

## September 30 browser demonstration

An isolated public ARGUS checkout launched governed job `job_cd87c2d28995` from Workbench. Its new 2D PNG SHA-256 was `c226a2f1b31ca5dec9ee7b5a5627716fc7e71561719813520993a1de7dbf426d`; its 3D Zarr manifest SHA-256 was `53a9ec97ce5e4c65a4cd4cd81643edc45a30067849631e494d4f2a94954633b1`. Both exactly matched the prior pinned private control receipt. The browser showed the completed 2D image and a selectable 3D slice. The worker exited. This is software/output parity on an exposed field, not an independent detector result.

The [machine-readable public verification](hecate/ARGUS_CONTROL_EXECUTION_20260930.json) records the input and output hashes, observed resource extremes, browser coverage and local full-receipt hash without distributing the control image or private workstation paths.
