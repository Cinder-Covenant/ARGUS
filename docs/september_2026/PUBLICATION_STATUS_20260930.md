# September publication receipt

Publication status checked September 30, 2026, at 20:49 UTC. This is a publication wrapper around the preserved prepublication evidence, not a change to its original receipts.

| Contribution | Published identity | Status at this check |
| --- | --- | --- |
| ARGUS source, runtime-isolation correction and evidence | `18cbbd3e079cf6cfb6278c8c9afdc7a5b773d37a` | Public main; all four [portable CI jobs passed](https://github.com/Cinder-Covenant/ARGUS/actions/runs/36774438341) |
| Villa renderer [#1901](https://github.com/ScrollPrize/villa/pull/1901) | `d7524301f7efe0fbf5a7e761b75fab498f68d5d3` | Open; no merge conflict reported; upstream review and remaining CI still pending |
| Hecate paired-output [PR #1](https://huggingface.co/scrollprize/hecate/discussions/1) | `24a28567c71ef9dd954a3367779c5f8a3481ad78`, based on `9cb86e500e944b11a06a7020403cde5dffb5bcb2` | Open upstream; three source/test files published; no checkpoint change |
| Villa input-form/numerical checks [#1897](https://github.com/ScrollPrize/villa/pull/1897) | `1be30608207beeb950cf2c10a220cf74fe0f888f` | Open |
| Villa supporting changes [#1896](https://github.com/ScrollPrize/villa/pull/1896), [#1902](https://github.com/ScrollPrize/villa/pull/1902) | Consult linked merge records | Merged |

At this check #1901's synthetic renderer regression and Linux compile/test jobs had passed. Windows, macOS and one analysis job were still running. Vercel reported deployment authorization required. That deployment failure is not a renderer regression, but it is still an unsuccessful external status and is not described as green CI. Consult the live PR for later results.

Anonymous HTTPS downloads of both public archives, the overview, the runtime module, and all three Hecate PR files matched the intended local bytes exactly. The check used no access credentials. See [machine-readable verification](ANONYMOUS_PUBLICATION_VERIFICATION_20260930.json).

Archive hashes:

- ARGUS evidence ZIP: `2eca22761b77701e6be27e6267065519ab4fb98c9cc1eb65e20f2e3685b61949` (236,119 bytes).
- Public Hecate contribution ZIP, including upstream MIT license: `95f6cb418d6cfc79a1b4e15c0fa256ab84596f27775e0a8b57bb75e33570e8db` (125,193 bytes).

The public evidence directory retains its original 29 payload files and manifest. The separate Hecate archive preserves its original source/test manifest and adds the upstream license. Earlier local-only statements are historical, not indications that the present links are inaccessible.

The accompanying combined description and URL list are prepared for one operator-submitted Progress Prize form. Publishing these files does not submit that form. No discovery claim or unread-target imagery is published.


## Status snapshot after 3bc1f68 -- 2026-10-01 01:13 UTC

ARGUS main advanced through commits eb34e4692e7bb9a5c09d2f89bf7e52b70c8433b1 and 3bc1f68494a6c1709ffc02a6ccd5a47d859109de. The final delivery CI run [36798529700](https://github.com/Cinder-Covenant/ARGUS/actions/runs/36798529700) passed its Node 22 UI build/unit tests and Python 3.11, 3.12 and 3.14 public test kits. The public research collection page adds a qualified catalog of the retained local CT/model resources; it does not publish the underlying 18.30 GB of CT chunks, 4.13 GB of checkpoints, target imagery or the private review packet.

One evidence follow-up was added to [Villa #1897](https://github.com/ScrollPrize/villa/pull/1897#issuecomment-5922534816), and a setup/reproducibility follow-up to [Hecate discussion #1](https://huggingface.co/scrollprize/hecate/discussions/1#6abdafab39f70bb1d81f0322). At this update, #1897 and #1901 remained open. Their current hosted checks included 8/18 passing respectively, 10/8 skipped, and a Vercel authorization failure on each; the code-related checks passed. #1896 and #1902 remained merged. The prize form had not been submitted.
