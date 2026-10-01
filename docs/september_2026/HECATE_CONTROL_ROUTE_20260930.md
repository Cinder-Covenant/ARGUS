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

## Physical preparation and bounded source correspondence

The retained surface-volume input is the PHerc0139 title positive-control surface at native 9.362 µm, using original Z planes `[3:24)` from the public 28-plane volume. Its [source metadata](https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHerc0139/segments/20260422000000-title_2026042222_zmid_flatboi/surface-volumes/9.362um-1.2m-113keV-volume-20250728140407.zarr/.zattrs) records isotropic spacing. The fixed crop is global `z[3:24), y[880:1168), x[2608:2896]` (the retained 21-plane extraction calls its first plane local `z=0`). The output grid uses `ratio = 9.6 / 9.362`, `z = (arange(16)-7.5)*ratio+10`, and `y/x = (arange(256)-127.5)*ratio+144` in crop-local coordinates. Preparation uses a float32 crop and SciPy `map_coordinates(order=1, mode="nearest", prefilter=False)`, then `rint`, clips to `[0,255]`, and casts to `uint8`.

The public preparation script accepts either the original 28-plane Zarr or the retained 21-plane `[3:24)` extraction. It writes into a new, non-overlapping directory and refuses unexpected metadata or output hashes. The verified script ran with NumPy 2.5.3, SciPy 1.18.1 and Zarr 3.3.0:

```powershell
$Runtime = "C:\path\to\pinned\runtime\Scripts\python.exe"
$SourceZarr = "T:\path\to\local\PHerc0139-title.zarr"
$Prepared = "T:\path\to\new\control-preparation"
& $Runtime scripts/prepare_hecate_pherc0139_control.py `
  --source-zarr $SourceZarr `
  --output-dir $Prepared
```

The expected `control_field_input.npy` SHA-256 is `3bdfab85fed733757ed3a0021f6240e02afb9bda9af9a12a7ef67c5ae156eb86`; the decoded `16×256×256 uint8` array SHA-256 is `b7d2f762e67031302eb55420851c4236e5d11696ff26639d1915bcdc94208ca6`.

The source verifier pins the public source metadata, preflights chunk lengths against a 16 MiB ceiling, then reads only the 12 chunks intersecting this crop. It accepts either the 28-plane volume or its 21-plane retained extraction and compares every selected crop pixel:

```powershell
$SourceReceipt = "T:\path\to\new\source-correspondence.json"
& $Runtime scripts/verify_hecate_control_source.py `
  --retained-zarr $SourceZarr `
  --receipt $SourceReceipt `
  --max-bytes 16777216
```

On this host, 12 chunks totaled 5,505,024 bytes; all 1,741,824 pixels in the `21×288×288` selected source crop matched exactly. The receipt records per-chunk hashes. This verifies only that crop, not the full volume or the Hecate input pixels after resampling.

## Strict runtime check and guarded Workbench route

Before starting ARGUS, generate a fresh local strict-load receipt with the already installed pinned runtime, provider and checkpoint. This loads the model but does not run inference. The script refuses changed provider/checkpoint hashes, an existing output receipt, inadequate resources or a different active Python interpreter. It uses the project single-flight resource guard, a 50% CUDA allocator cap and two CPU threads:

```powershell
$Runtime = "C:\path\to\pinned\runtime\Scripts\python.exe"
$ProviderDir = "C:\path\to\providers\hecate\9cb86e500e944b11a06a7020403cde5dffb5bcb2"
$RuntimeReceipt = "T:\path\to\new\private-runtime-receipt.json"
& $Runtime scripts/verify_hecate_strict_load.py `
  --runtime-python $Runtime `
  --provider (Join-Path $ProviderDir "hecate.py") `
  --checkpoint (Join-Path $ProviderDir "hecate_9.6um.pth") `
  --receipt $RuntimeReceipt `
```

Admission floors are 10 GiB available RAM, 1.25 GiB whole-GPU free memory, GPU below 70 °C, C: at least 50 GiB free and T: at least 85 GiB free; the process requires at least 8 GiB RAM and the guard watches RAM, VRAM and temperature. No model weights or CT are packaged.

On October 1, 2026, this exact public script loaded the pinned runtime in 3.981 seconds, confirmed the `(16,64,64)` / 9.6 µm contract and wrote `STRICT_LOAD_PASSED`; no inference ran. Available RAM changed from 15.245 to 14.485 GiB, free VRAM from 4806 to 4101 MiB, and temperature stayed at 50 °C. The sanitized [strict-load receipt](hecate/HECATE_STRICT_LOAD_20261001.json) omits machine paths.

Set the environment variables in “Configure the retained input” before starting the ARGUS services. In Workbench, select PHerc0139, choose **Hecate output**, review the exact plan, and approve the governed control. The output directory must be a fresh child of `ARGUS_REPO\artifacts`; output receipt paths resolve through that same configured artifact root even when the installed source tree is elsewhere. The launch refuses any changed control array, mismatched preparation, provider, checkpoint, runtime receipt or scroll identity.

The September 30 browser demonstration below is the completed run for this campaign. Do not repeat it merely to refresh the timestamp. During this release review, the existing local Workbench route showed the stored completion receipt, output preview and 3D depth slider; no inference worker was running during this recheck.

## September 30 browser demonstration

An isolated public ARGUS checkout launched governed job `job_cd87c2d28995` from Workbench. Its new 2D PNG SHA-256 was `c226a2f1b31ca5dec9ee7b5a5627716fc7e71561719813520993a1de7dbf426d`; its 3D Zarr manifest SHA-256 was `53a9ec97ce5e4c65a4cd4cd81643edc45a30067849631e494d4f2a94954633b1`. Both exactly matched the prior pinned private control receipt. The browser showed the completed 2D image and a selectable 3D slice. The worker exited. This is software/output parity on an exposed field, not an independent detector result.

The [machine-readable public verification](hecate/ARGUS_CONTROL_EXECUTION_20260930.json) records the input and output hashes, observed resource extremes, browser coverage and local full-receipt hash without distributing the control image or private workstation paths.
