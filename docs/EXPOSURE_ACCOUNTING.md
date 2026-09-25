# Exposure accounting

Two questions decide whether a model result means anything on a scroll:

1. Are these models independent evidence, or do they share ancestry (a teacher, a pseudo-label
   source, an initial checkpoint)?
2. Is this scroll genuinely held out for this model, on every path by which data can reach a
   model's weights?

`argus exposure` records what public sources say about both, keeps what was stated apart from
what was inferred, and refuses to call anything held out unless every path is verified clean. It
extends `argus/core/exposure.py` (per-channel vocabulary, "unknown is never clean") and the
public official survey (`argus/public_official_survey.json`, scroll identity). Code:
`argus/core/exposure_accounting.py`, `argus/cli/cmd_exposure.py`.

## The four channels

For every (model, physical scroll):

| channel | meaning | `argus.core.exposure` channel |
|---|---|---|
| `direct_labels` | supervised labels on that scroll | `SUPERVISED_LABEL` |
| `teacher_labels` | a teacher model's predictions or labels | `TEACHER_PREDICTION` |
| `pseudo_label_lineage` | pseudo-labels, or guidance derived from another model | `PSEUDO_LABEL` |
| `raw_ct_pretraining` | self-supervised pretraining on raw CT, including inherited initial weights | `RAW_VOLUME_PRETRAINING` |

A parent's exposure flows to a child through the edge kind that links them: `INIT` (weights
continued from the parent) into `raw_ct_pretraining`, `TEACHER` into `teacher_labels`,
`PSEUDO_SOURCE` into `pseudo_label_lineage`. The path is kept, so a report can say through which
ancestor a scroll was reached.

## Physical-scroll identity

Rescans, aliases, volume ids, scan ids, segment names (`<segment>-on-<volume id>-<pitch>um`) and
store URLs resolve to one physical scroll through the public survey, so an exposed 2 um rescan
makes the scroll not held out at 9 um. Names that share a stem (a scroll and a fragment or sibling
piece: `PHerc9001` and `PHerc9001P`) are linked as INFERRED "possibly the same physical object".
That link never proves exposure and is never ignored: exposure on one blocks the other as
`EXPOSURE_POSSIBLE`. A name that resolves to nothing blocks every channel that mentions it.

`argus exposure resolve NAME` shows how a name resolves.

## Source status, per claim

- `VERIFIED`: a cited public source states it. The record must carry the source's https URL and
  retrieval date; a `VERIFIED` claim without both is downgraded to `UNVERIFIED` and reported.
- `INFERRED`: derived, with stated reasons. Never treated as verified, and never lets a scroll
  pass.
- `UNVERIFIED`: the default. A channel no source speaks about is `UNVERIFIED`.

## Fail-closed eligibility

`argus exposure check RECORD --model M --scroll S` returns `ELIGIBLE_AS_HELD_OUT` only when all
four channels are `CLEAN` (VERIFIED-absent), including through every ancestor. Anything else is
`NOT_ELIGIBLE`, with the channel states and reasons. A verdict also maps onto the existing
vocabulary (`MODEL_HELDOUT_ELIGIBLE`, `DEVELOPMENT_ONLY`, `INDETERMINATE`).

Absence is proved by a `VERIFIED` claim of kind `absent` (a source states the channel is not
used), or by `exposed_set_complete` (a source lists every scroll used on that channel) that does
not contain the scroll.

## Lineage components under a declared rule

The rule is written into the record (`shared_ancestry_v1`) and into every report. Entries join a
component when a chain of ancestry edges connects them; sharing a training scroll does not join
them and is reported apart. Counts are given at two strengths (VERIFIED edges; VERIFIED plus
INFERRED edges) and always as a join statement, for example:

> N of M registered entries joined the same lineage component under rule shared_ancestry_v1
> (VERIFIED edges only). Entries that are not ink detectors are counted separately by role.

Entries without recorded ancestry sit in singleton components. That is the absence of a record,
not evidence of independence.

## Record format (`argus-exposure-record-v1`)

```json
{
  "schema": "argus-exposure-record-v1",
  "rule": "shared_ancestry_v1",
  "sources": {"card": {"url": "https://example.org/model-card", "retrieved": "2026-09-01"}},
  "identity_aliases": [],
  "models": [{"id": "student", "role": "ink_detector"},
             {"id": "teacher", "role": "teacher", "released": false}],
  "claims": [
    {"id": "c1", "model": "teacher", "channel": "direct_labels", "kind": "exposed",
     "scroll": "PHerc0139", "status": "VERIFIED", "source": "card"},
    {"id": "c2", "model": "student", "channel": "direct_labels", "kind": "absent",
     "scroll": "*", "status": "VERIFIED", "source": "card"}
  ],
  "edges": [{"child": "student", "parent": "teacher", "kind": "TEACHER",
             "status": "VERIFIED", "source": "card"}]
}
```

```
argus exposure validate record.json
argus exposure check  record.json --model student --scroll PHerc0814
argus exposure report record.json --scroll PHerc0139 --scroll PHerc0814 --scroll PHerc0009B --markdown
argus exposure graph  record.json --svg
```

Output is deterministic JSON (`argus-exposure-report-v1`) or markdown. Nothing is fetched and
nothing is run; the record is whatever you assembled and cited.

## Disclosure boundary

Public: this generic mechanism, the record and report formats, and records built from public
sources, queried on scrolls that are not prize targets. Not public: which scrolls or detectors an
operator would pick, any priority ranking, and eligibility results for prize-set scrolls. The tool
refuses prize-set scrolls as queries (`NOT_EVALUATED_HERE`), masks them in output, and treats an
id that shares a stem with a prize-set scroll as not eligible without reporting anything about
the prize-set scroll.

## What this does not show

It does not measure leakage or score inflation, does not say a model is good or bad, and does not
establish independence. It shows what public sources state, what follows from it under a declared
rule, and where the sources are silent.
