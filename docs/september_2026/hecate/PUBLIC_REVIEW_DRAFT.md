# Hecate: reuse shared features for paired 2D and 3D output

Prepared for upstream review; not yet published. Based on [scrollprize/hecate revision 9cb86e500e944b11a06a7020403cde5dffb5bcb2](https://huggingface.co/scrollprize/hecate/tree/9cb86e500e944b11a06a7020403cde5dffb5bcb2), still the provider's current revision when checked on September 30.

## Change

When a CLI request specifies both `--output` and `--output-3d`, the existing implementation computes the feature network twice for each tile. This candidate computes features once, applies the existing attention-based 2D projection and 3D head, and blends each result with the same Hann weights. The checkpoint and the single-output branches are unchanged.

The patch consists of a paired-output CLI branch and one sibling helper. It preserves center-depth selection, reverse-depth placement, blank support, overlap weighting and uint8 probability conversion. The helper uses disk-backed accumulators. It does not change detector accuracy or qualify a detector for unread scrolls.

## Actual CLI measurement

Three alternating baseline/candidate process pairs used the retained PHerc0139 exposed control field, shape 16x256x256, nominal 9.6 micrometer sampling, Hecate 9.6 checkpoint, FP32, batch one, stride32, two CPU threads, GTX1660Ti6GiB. Each CLI performed its own tiling and PNG/Zarr serialization.

| Pair | Baseline seconds | Shared-feature seconds | Decoded outputs |
|---|---:|---:|---|
| 1 | 17.7276 | 11.8082 | Bitwise equal |
| 2 | 17.8398 | 11.5913 | Bitwise equal |
| 3 | 17.8357 | 11.5882 | Bitwise equal |
| Median | 17.8357 | 11.5913 | 35.01% less elapsed time |

Each pair matches all65,536 2D pixels and1,048,576 3D voxels. Feature calls fall from98 to49. The common resource guard checks before feature evaluation; both sides include these hooks, identity checks, imports, model loading, tile preparation, inference, blending, writes and process exit. Raw-source resampling and UI transport are excluded. Fresh processes do not imply a cold OS cache.

Starting temperatures52–54C; maximum68C; no cooling pause. Minimum available system RAM13.926GiB, minimum whole-GPU free memory4003MiB, peak process-tree RSS1.541GiB. All six processes exited0 and were checked absent. This is one control field and one GPU, not a whole-scroll or2D-only throughput claim. PHerc0139 is development-exposed, not an independent accuracy holdout.

## Files to review

- `PROVIDER_CANDIDATE.patch`: source patch, SHA256 `225436764093e619d16531e9a4561890690dc064049e174ebac61407c9477a1d`.
- `PROVIDER_TESTS.patch`: four portable synthetic tests, adapted from the existing tests solely by changing the sibling import.
- `hecate.py`: proposed source SHA256 `d02029db394ab4a912ecd9433dbd76e86a812cfc65eb28890f979bc381310ca2`.
- `hecate_shared_output.py`: SHA256 `b01468876bf3c528a6c633dc358379130bb8a9686a1044084339a2a6c4d2f4ad`.
- `test_hecate_shared_output.py`: SHA256 `4e51f3c26a7d1d76a84b28157aeff9781dc41adb7ae7b512022d223b8d4ef041`.
- `CONTROL_CLI_FRESH_PROCESS_256_20260930/ACTUAL_CLI_PARITY_RESOURCE_RECEIPT.json`: original measurement receipt, SHA256 `3fc2bbbdfe65a8c7f3b304ef9146b9c4165a920ed6b948c5e79e1fd878521426`.

The original full receipt and guarded launch source are retained locally. They contain workstation paths and the harness binds to local assets; they are not a portable benchmark command. Publication should include a reviewable evidence export and the exact input recipe below. No target imagery, CT arrays or checkpoint binaries are needed in the code contribution.

## Portable software check

In a checkout of the pinned provider, with its documented dependencies and pytest:

```text
git apply --check PROVIDER_CANDIDATE.patch
git apply PROVIDER_CANDIDATE.patch
git apply PROVIDER_TESTS.patch
python -m pytest -q test_hecate_shared_output.py
```

Four tests pass with CUDA disabled. They exercise head equivalence, margin handling, partial/blank support, irregular edges/overlap, center-depth selection and reversal. A separate source-only patch application reproduced the reviewed source/test hashes exactly. No scroll data or weights are required for these tests. They are software checks, not ink controls.

## Control reproduction

Public source: [PHerc0139 title segment surface-volume metadata](https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHerc0139/segments/20260422000000-title_2026042222_zmid_flatboi/surface-volumes/9.362um-1.2m-113keV-volume-20250728140407.zarr/.zattrs), array `0`, shape28x1780x5360, uint8,9.362micrometers. The retained array uses original z[3:24). Metadata was checked live; remote chunk bytes have not been independently compared against the retained bytes.

Take the retained crop z[0:21),y[880:1168),x[2608:2896). Sample float32 coordinates `(arange(16)-7.5)*(9.6/9.362)+10` in Z and `(arange(256)-127.5)*(9.6/9.362)+1024/+2752` in Y/X. Subtract the crop origin. Use SciPy `map_coordinates(order=1,mode='nearest',prefilter=False)`, round-to-nearest with NumPy `rint`, clip0–255 and cast uint8. Expected decoded input SHA256: `b7d2f762e67031302eb55420851c4236e5d11696ff26639d1915bcdc94208ca6`. A mismatch is unresolved reproduction.

The provider and candidate use the same CLI arguments, separate outputs and checkpoint SHA256 `809f4f10f7cb7afa19b4bee0f7d2ab31edd7e11b664f9f210cc9c17f22fcfe5d`:

```text
python hecate.py --checkpoint hecate_9.6um.pth --input control_field_input.npy --output fresh_run/prediction.png --output-3d fresh_run/prediction_3d.zarr --spacing-um 9.6 --device cuda --batch-size 1 --stride 32 --precision fp32
```

Use appropriate external resource supervision; the bare CLI does not enforce the workstation's RAM, total-VRAM or temperature floors. The original comparison used identical guardian hooks on both implementations. Expected decoded output SHA256: 2D`7494ed767591367e453efec4d89563926da4262a7d52836863c11e0b0c227ec5`,3D`b5a52d0bce49ac74cbac3428032694bc975c84e4a7b23d6b70ae8af7255f89d6`.

## Limits and attribution

Hecate's architecture, checkpoint, preprocessing, heads and baseline CLI belong to their upstream authors. This contribution shares their feature computation across a paired request. The2.4micrometer model, BF16, other GPUs and whole-scroll execution have not received this measured validation. Synthetic margin tests are not hardware validation of that model. There is no confirmed unread-scroll discovery in this result.
