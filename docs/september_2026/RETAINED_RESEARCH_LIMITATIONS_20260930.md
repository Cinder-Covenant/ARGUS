# Retained research: transfer checks, corrections and a mixed topology cohort

Team Cinder Covenant — September 30, 2026.

This is an **archival summary**, with corrections identified during release review. It does not add a new inference result, improve detector accuracy, establish readable text or provide a fully reproducible comparative benchmark. The original result JSONs, source snapshots, CT/label arrays and topology assets discussed below are not included in this public export. Local locators and SHA-256 values identify the retained evidence; they are not public download links.

The useful lesson is specific: a successful exposed control and a large collection of finite predictions do not establish performance on another physical scroll. Equally, a negative result needs its own preparation, scoring and provenance checks before it supports a broad conclusion.

## September 6 checkpoint checks: descriptive results only

N-1444 and N-1445 examined the released ink_9um hybrid_3d2d family: seven checkpoints for each of two seeds. The additional dense-label checkpoint in those files is a separate training run and is excluded from the fourteen-checkpoint counts below. PHerc0139 w035 was an in-manifest control. The other preparations were declared outside that training manifest.

| Retained check | Population used by each family checkpoint | Recorded outcome |
| --- | --- | --- |
| N-1444, PHerc0139 w035 control | In-manifest calibration material | 13/14 exceeded the stated control AUC floor of 0.90 |
| N-1444, PHerc0841 w00 | 120 qualifying patches across six selected windows | 0/14 reached the stated 0.80 transfer gate; checkpoint patch-median AUCs ranged 0.518728–0.578302 |
| N-1445, PHerc0009B | 164 qualifying patches in one retained region | 0/14 reached the stated 0.80 gate; checkpoint patch-median AUCs ranged 0.464715–0.570719 |

These are summaries of the saved metrics, checked against the original JSONs on September 30. They are **not new, tie-correct rescoring of retained predictions**. The N-1444 receipt is dated September 6 at 21:49:42 UTC; N-1445 is dated 22:02:11 UTC. They do not establish that the scrolls lack ink, that every checkpoint is statistically indistinguishable from chance, or that this was the first fourteen-checkpoint benchmark. Prior checkpoint benchmarking must receive its own credit.

### Corrections and remaining limitations

1. **The N-1444 decision code differs from its preregistered prose.** The prose requires every family member to be within the 0.45–0.55 target band while clearing the 0.90 control floor. The implementation sets `family_fails` whenever no checkpoint reaches 0.80. Only 8/14 recorded target medians lie within the stated chance band, and only 13/14 clear the control floor. The descriptive gate counts above stand as recorded; the stronger claim that the prose condition was satisfied does not.
2. **The historical AUC scorer does not average tied ranks.** N-1444 uses `argsort().argsort()`; N-1445 reuses that function. Its treatment of tied predictions can change the statistic. A corrected value cannot be inferred from the retained medians. The inspected run directories retain inputs and summary receipts; no saved per-patch prediction arrays were identified there for CPU-only rescoring. This is an unresolved scoring limitation, not a demonstrated numerical size of error.
3. **Representation differs along with scroll identity.** The PHerc0139 control used a 9.596 micrometer pyramid product; PHerc0841 used locally prepared material from a 9.366 micrometer acquisition. PHerc0009B used a pyramid product at 8 micrometers. N-1445 therefore supplies an additional preparation, not an exact resolution-matched causal test of physical-scroll transfer. Original claims that it completely settles representation versus generalization are too strong.
4. **Source preservation differs between checks.** N-1444's retained source hash matches its preregistration. N-1445's current source is available locally, but its original receipt does not bind that source hash. Pinning today's source does not retroactively establish launch-time provenance.

## September 7 follow-up: preserve the erratum and the source gap

N-1454's original `results_heldout.json` used seven surface keys in a decision intended for two physical scrolls. N-1455 preserves that result and corrects its interpretation: the original 0.387690 worst value was a **window**, not the worst scroll.

The erratum reports PHerc0009B's family median as 0.530250, with reported interval 0.481819–0.545428. PHerc0841's corrected 0.493182 is explicitly an approximation formed from window medians; the original per-patch values needed for the declared pooled statistic were not retained in that result. These reported intervals are not newly validated uncertainty estimates. The historical decision remains failed under its stated gate, but the approximation must accompany any quotation of the PHerc0841 number.

Two additional provenance problems were identified during the September 30 review:

- `n1453_input_binding_20260906.py` appends the arrays from `N45.target_0009b()`, then writes N44's PHerc0841 path constants into every surface's metadata. This explains the PHerc0009B entry's wrong paths in `INPUT_BINDING.json`. The inspected code demonstrates a path-metadata defect; it does **not** establish that PHerc0841 arrays were substituted for PHerc0009B. Independently confirming historical physical-source identity still requires the importer bindings and matching array digests.
- N-1454's result names launch-source SHA-256 `dff31efaeaa981f6e3908789fd5038410ae555239fccd67b0d7142d8e31794d6`. The inspected current script, preservation manifest and Git snapshot instead identify `d156f208243f9e6da3f1f616bd257f0dbf00b2c57aa8e813e69e1318fbadb3e2`, which includes the later aggregation repair. The selected history search did not recover launch bytes. The repaired source cannot be presented as the exact source of the historical run.

These limitations prevent describing this follow-up as an exact executable reproduction. Original receipts are preserved; this document corrects the release interpretation without changing them.

## September topology cohort: mixed results, no general area gain

The frozen cohort selected 23 public surfaces. Twenty-one were processed, with identical replay outputs reported for all 21. Seventeen surfaces had paired measurable flattening results; four had timeouts in both arms, and two selected surfaces were not run.

On the 17 measurable surfaces, accepted chart area totaled 234.50 square centimeters versus 208.87 for whole-surface flattening under the experiment's frozen geometric criteria. The apparent gain depends entirely on one PHerc0139 w026 baseline failure. Excluding that surface, chart area was approximately 194.6 versus 208.9 square centimeters. Another surface changed from a passing baseline to a chart failure. The four timeout cases include the largest meshes and are not evidence of successful flattening.

This supports an actionable mixed-result report about crease exclusion, overlap criteria, determinism and timeout limits. It does not demonstrate a general increase in usable area. No CT sheet-continuity validation was performed for this cohort, so geometric acceptance cannot establish a correct papyrus sheet or improved reading.

The public ARGUS topology metric is not the complete `surface_qualify` plus SLIM cohort execution path. That full tool/runtime is not packaged here; no public end-to-end replay is claimed.

## Retained source index

Hashes below were read from the original local files during this release review. A hash permits byte-identity checking when the file is available; it does not by itself establish scientific correctness or launch-time provenance.

| Evidence | Original local locator | SHA-256 |
| --- | --- | --- |
| N-1444 results | `T:/Dev/vesuvius/artifacts/n1444_checkpoint_family/family.json` | `9a7df02eb4c06b157f5a0e550791614f55312ead997418dbfd08ff3b92400fdf` |
| N-1444 source, matching preregistration | `T:/Dev/vesuvius/scripts/n1444_checkpoint_family_20260906.py` | `2d715fcc0f09d9d869adbdb5d2ef6debb34aa72c1af535c7e0066c6883f3dee5` |
| N-1445 results | `T:/Dev/vesuvius/artifacts/n1445_heldout/heldout.json` | `e9a237a5e6ee940f082ad5b41447b017b9d6753d7869e6a824b84f7fae6c6545` |
| N-1445 current source; not launch-bound | `T:/Dev/vesuvius/scripts/n1445_heldout_representation_20260906.py` | `0efaaf8fd6c7ec5463ac033bbfeb38a0f233a3d6d8e0c570843e0676428e4f03` |
| N-1454 results | `T:/Argus/repo/artifacts/n1452_heldout/results_heldout.json` | `4dea4dbf6d0142289bdca1928dd3fb72eccddf3b89b49e6b7bf433adcfd72d6c` |
| N-1453 input binding | `T:/Argus/repo/artifacts/n1452_heldout/INPUT_BINDING.json` | `62d14d35de39d848f4da0a2d69628f3521d2fbbbfe180c0f4ad95e7818be1ac7` |
| N-1453 binder source, matching binding | `C:/Argus/scripts/n1453_input_binding_20260906.py` | `f75a90fe5aada9999a561e2ccc0d97000759dc8cd900acb27a1a04a712ef3ba0` |
| N-1455 aggregation erratum | `T:/Argus/repo/artifacts/n1452_heldout/ERRATUM_01_aggregation.json` | `a5945f29f4dc63bd199cf5c05ced211301a9bb03fece12eb614cab9ea6269458` |
| Topology frozen cohort | `T:/Argus/artifacts/topology_cohort_20260926/COHORT_MANIFEST.json` | `ea30767d266e9194f6b7783cee797ec299a6f00a13ab186f9e7f3f67213ec3ae` |
| Topology result table | `T:/Argus/artifacts/topology_cohort_20260926/RESULTS.csv` | `9d850f92ac9197f290ce21dec7449695c1b68d3219967663482c86d43585a4d6` |
| Topology interpretation and amendments | `T:/Argus/artifacts/topology_cohort_20260926/GO_NO_GO.md` | `a3454148fe9829e67c92a6da2716ed63db36b6c520e4b6880ca643c6919cb9a4` |

The table counts and ranges can be regenerated from those retained JSON/CSV files without inference. They cannot currently be replayed from this public appendix alone. A public corrected benchmark would additionally require distributable inputs or acquisition bindings, preserved execution source, a validated scorer, saved predictions or separately authorized inference, dependency pins and an explicit statement of exposure and preparation differences. No new inference, training or target-data access was performed to prepare this summary.
