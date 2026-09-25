# Sources for EXAMPLE_EXPOSURE.json

Every VERIFIED fact in EXAMPLE_RECORD.json cites one of these. All retrieved 2026-09-25 (UTC) with
`curl` (Hugging Face `raw/main/README.md`, GitHub contents API) and, for ink_9um, also WebFetch.
The retrieved texts are not redistributed here (their licences were not checked); fetch the URLs to compare. The revision is the commit sha the URL resolved to at retrieval time.

| key | URL | revision |
|---|---|---|
| ink_9um | https://huggingface.co/scrollprize/ink_9um | 7109667e2607db1b90c37c8b09cb876ea7fe7bb1 |
| ink_canonical_2um | https://huggingface.co/scrollprize/ink_canonical_2um | 075855bc69317ef6febf39a0d9d687b27d2b7c29 |
| ink_3d_dino_guided | https://huggingface.co/scrollprize/ink_3d_dino_guided | 73a79525466037432191284dfa237baf830c49ec |
| dinovol_v2_ps8_with_paris4_352500 | https://huggingface.co/scrollprize/dinovol_v2_ps8_with_paris4_352500 | 6a8cccbafef191a966da815e22ff5c6eae075aae |
| dinovol_v2_ps8_supcon3class_step362500 | https://huggingface.co/scrollprize/dinovol_v2_ps8_supcon3class_step362500 | 983bf00da2a9a9179078e705f96ae79d28af113d |
| dinovol_v2_ps6_step032350 | https://huggingface.co/scrollprize/dinovol_v2_ps6_step032350 | 2ad412b7bc4ae8f742b811f8d8017381802a1788 |
| fiber_selftrain_teacher_epoch30 | https://huggingface.co/scrollprize/fiber_selftrain_teacher_epoch30 | 08ef7a88ab710770c5b961ee39df1879333a2aa9 |
| fiber_dinoguided_2class_step010000 | https://huggingface.co/scrollprize/fiber_dinoguided_2class_step010000 | 65e72d37a61170ed5b46494c55da09b5025bd6a4 |
| fiber_ink_4class_selfdistill | https://huggingface.co/scrollprize/fiber_ink_4class_selfdistill | ec9bbc4dbc65a052fc4d78429f7ce5eff080aafe |
| ink_9um_dataset | https://huggingface.co/buckets/scrollprize/datasets/tree/ink_9um (README.md fetched from .../resolve/ink_9um/README.md; uploadedAt 2026-08-14T01:04:39Z) | bucket object, no commit sha |
| villa_prior | https://github.com/ScrollPrize/villa/blob/3ea17f54a9b3d5fd1aaf73e1d2c8386dbaa9f30e/ink-detection/configs/aligned21_fixed_scroll_prior.json | branch merge-ink-pipelines @ 3ea17f54 |
| villa_readme | .../configs/README.md (same commit) | 3ea17f54 |
| villa_hybrid | .../configs/aligned21_hybrid_3d2d.json (same commit) | 3ea17f54 |

Scroll identity is normalised through argus/public_official_survey.json (checked_at 2026-09-25T11:34:46Z).

## What each source states (the load-bearing sentences)

- ink_9um card: trained on "PHerc. 0139 (9), Scroll 1667 (6), PHerc. Paris 4 (8), and PHerc. 0814 (1), plus 5 native 9.362 um segments from PHerc. 0139"; per-batch quotas 29/22/11/2 of 64. The Villa prior file lists 29 representations = 10 + 6 + 8 + 1 physical segments (0139:w016...w044, 1667:w013...w031, Paris4:w00...w09, 0814:46527). The card says "9" for 0139 and the prior file lists 10 physical keys; the dataset README explains it: 9 aligned 2.4 um segments plus 5 native 9.362 um segments, of which w044 is the tenth physical segment. The card is silent on teachers, pseudo-labels and pretraining; the recipe file is a template with placeholder paths and names no initial checkpoint.
- ink_3d_dino_guided: "Trained in stages: (1) teacher on 8-scroll surface-conditioned ink labels (PHerc. Paris 4, 0139, 0500P2, 0814, 0841, 1667, MAN5, 9B); (2) a DINO-guided student using dense ink-likeness from ... dinovol_v2_ps8_with_paris4_352500; (3) + background masking; (4) self-distillation." Reference embedding averaged from 256 expert-clicked tokens; their scroll is not stated.
- dinovol_v2_ps8_with_paris4_352500: "Self-supervised on 11 open-data Herculaneum volumes" (list of 11), "Pretraining only - no finetuning / segmentation head is included."
- dinovol_v2_ps8_supcon3class_step362500: continues from step 352500 of the above; "Training data for this stage: crops from PHercParis4 and PHerc0332"; label source described by its publisher as a "well-supported inference", not confirmed.
- fiber_selftrain_teacher_epoch30: warm-start and dynamic pseudo-label source of fiber_dinoguided_2class; earlier ancestry only suggested by a file name.
- fiber_dinoguided_2class_step010000: "Trained on PHerc. Paris 4"; label-free self-training; pseudo-labels from the selftrain teacher and a DINO-similarity map from the supcon backbone.
- fiber_ink_4class_selfdistill: "Trained on PHerc. Paris 4"; two frozen teachers; fiber teacher "very likely" fiber_dinoguided_2class (not proven byte-identical); ink teacher unrecoverable.
- ink_canonical_2um and dinovol_v2_ps6_step032350: no training-data statement at all.

- ink_9um dataset README: labels are 'annotations [that] originate from the Vesuvius Challenge ink annotation dataset and were transferred onto the public surface volumes with the tifxyz_label_transfer scripts'; it lists 24 aligned + 5 native segments over PHerc0139, PHerc1667, PHercParis4, PHerc0814 and states three validation-mask segments (pherc0139-w016, pherc0814-46527, pherc1667-w029) on those same scrolls. It also fixes 'Scroll 1667' = PHerc1667.

## Not retrieved

The paper (arXiv:2606.29085) and Supplementary Table 4 were not read. Those may state more; until read, the corresponding channels stay UNVERIFIED or INFERRED.
