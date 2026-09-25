# Exposure accounting: a real-data example

This directory is a worked example of `argus exposure` (see `docs/EXPOSURE_ACCOUNTING.md`) on
public information only. `EXAMPLE_RECORD.json` was assembled by hand from the nine released
`scrollprize` Hugging Face checkpoint cards and the Villa `merge-ink-pipelines` config files,
retrieved 2026-09-25. Every VERIFIED fact in it cites a URL and retrieval date (see `SOURCES.md`).
Nothing in the tool fetches anything; the record is the input, and the other files are outputs.

## Regenerate the outputs from the record

Run from the repository root, with the ARGUS environment active:

```
argus exposure validate docs/exposure_example/EXAMPLE_RECORD.json

argus exposure report docs/exposure_example/EXAMPLE_RECORD.json --scroll PHerc0139 --scroll PHerc0814 --scroll PHerc0009B --scroll PHerc0841 --scroll PHerc0332 --scroll PHerc0172 --json > EXAMPLE_EXPOSURE.json

argus exposure report docs/exposure_example/EXAMPLE_RECORD.json --scroll PHerc0139 --scroll PHerc0814 --scroll PHerc0009B --scroll PHerc0841 --scroll PHerc0332 --scroll PHerc0172 > EXAMPLE_REPORT.md

argus exposure graph docs/exposure_example/EXAMPLE_RECORD.json --svg > evidence_graph.svg
```

The outputs are deterministic. Compare against the files here ignoring line endings (a Windows
shell writes CRLF; the files here are LF). The record hash printed in the report
(`312e9f6c2e1e6ed7`) should match.

## What the example shows

- Under the declared rule `shared_ancestry_v1` (a chain of recorded INIT / TEACHER /
  PSEUDO_SOURCE edges), 5 of the 9 registered entries joined the same lineage component when only
  VERIFIED edges count, and 6 of 9 when INFERRED edges count too. Of the 5, one is an ink
  detector; the others are counted separately by role (2 backbones, 2 fiber segmenters). The
  detectors, fiber segmenters and backbones are never pooled into one "N detectors" figure.
- Registered entries that joined no component are singletons. A singleton means no ancestry was
  recorded; it does not mean the entry is independent. The public cards are often silent about
  teachers and pretraining.
- Sharing a training scroll does not join components. Scrolls named by more than one entry are
  listed separately.
- 0 of the 54 (model, scroll) held-out queries (9 entries x 6 scrolls) are eligible. The rule is
  fail-closed: a scroll is eligible only if all four channels (direct labels, teacher labels,
  pseudo-label lineage, raw-CT pretraining) are VERIFIED absent, through every ancestor, and the
  public sources are silent on at least one channel for every pair. This says the public
  sources are too silent to certify any of these scrolls as held out for these checkpoints. It
  does not say any of them is contaminated.

## What the example does NOT show

- Not a measurement of leakage, score inflation, or how much any exposure changed any result.
- Not a claim about what the checkpoint authors did beyond what their cards say; the role labels
  (`ink_detector`, `fiber_segmenter`, `backbone`) are this record's classification, and a reader
  may classify differently.
- Not complete: the associated paper and its supplementary tables were not read. Where they may
  speak, channels stay UNVERIFIED or INFERRED, and INFERRED never lets a scroll pass.
- Not about the official prize targets. The tool refuses to evaluate prize-set scrolls
  (`NOT_EVALUATED_HERE`); the example's queries are non-prize scrolls.
- The retrieved card texts are not copied here (licences not checked); cite the URLs.
