# Narayanan-Shmatikov propagation on two real Bitcoin views

> **This is a seed-assisted experiment, not an independent attack.** The seeds below were drawn
> from the withheld correspondence — the same map the run is graded against. Every row is stamped
> `seed_provenance: "withheld-correspondence-sample"` in `results/artifacts/ns-bitcoin-v1.json`. It measures how
> far propagation carries an identity it was *handed*; it is not evidence that the identity could
> have been found. The independent-label path was tried first and yielded zero usable seeds
> (below), which is why the fallback is what is reported.

**Sample limit stated up front.** Two adjacent 120-block windows of the 2016 chain: heights
391,992-392,111 (133,576 transactions) and 392,112-392,231 (157,724 transactions), read from
`data/epochs_2016_weekly/`. That is roughly 40 hours of chain, not a chain-wide or
time-representative population, and the export carries **addresses only** — no prevout values and
no script types — so the clustering below is plain common-input ownership with the coinjoin shape
refused, and the amount and fingerprint channels are absent by construction, not by choice.

**Which algorithm.** `decluster/baselines/narayanan_shmatikov.py`: the 2009 topology-only
propagation scoring kernel — direction-aware degree-normalised neighbour votes, eccentricity over the
**unclaimed** candidate population including its implicit zeros, a mandatory reverse match, iterated
to convergence. The population is a genuine ambiguity in the source rather than a choice made
against it: the paper's prose scores "each unmapped node in v2", while its pseudocode two pages
later initialises one score per right vertex and leaves the claimed ones at zero. Both readings are
implemented (`population="unmapped"` / `"all"`); the default, and what is run below, is the prose.
Seeds are supplied rather than found by the paper's clique search, and accepted nodes are not
revisited/remapped as the paper's prose specifies. No vertex attributes, no edge attributes, no hub
filter, no rarity weights.

The repo's older cross-view numbers are not this attack's and none are reused here, but they come
from two different places and were previously credited to one. `RESULTS-view-match-2026.md` — and
the "one match in 15,688" figure, which is `RESULTS-multiepoch-local-2016.md`'s — come from
`decluster/view_match.py`, a **different, experimental** matcher. `RESULTS-graph-deanon.md` comes
from `decluster/graph_deanon.py`, which is not a matcher at all: it is common-neighbour link
prediction scored pairwise on a single graph, with no seed set, no vertex correspondence, no
propagation and no second view.

## The two views, and why one adversary holds both

| | view A | view B |
|---|---|---|
| source | `epoch_2016_01_391104-392111.ndjson.gz` | `epoch_2016_01_392112-393119.ndjson.gz` |
| heights | 391,992-392,111 | 392,112-392,231 |
| transactions | 133,576 | 157,724 |
| vertices (degree >= 2) | 88,066 | 104,328 |
| edges | 163,567 | 189,919 |

Both windows are public chain, so *observation* is not what is partial here — the **clustering**
is. The two windows are clustered together (one global common-input lookup over both, so a cluster
keeps one identity across the boundary), and the 8,030 clusters whose addresses straddle the
boundary are then contracted under a **separate pseudonym in each view**
(`views.split_clusters_by_view`): `C#a` in A, `C#b` in B. That is the framework's premise made
concrete — one owner, two pseudonyms, unlinked — and the adversary who holds both views is anyone
who observed the chain across a clustering discontinuity, which is the ordinary condition of an
incomplete clustering, not a privileged position. Because each view is contracted under its own
lookup, **no pseudonym string appears in both views**, so the trivial identity match does not
exist and the only correspondence available is one propagation has to rediscover.

Stated observation policy, because it sets the population: 613,448 addresses were clustered; each
view keeps the vertices whose degree **in its own view** is at least 2. The filter is per-view and
consults neither the other view nor the correspondence; degree below 2 is a vertex propagation can
neither match nor bridge through.

**Withheld correspondence** — it takes no part in view construction, in seeding the independent
path, or in any score the algorithm computes. It is used for grading, for drawing the seed-assisted
seeds below (which is why those rows are stamped as such), and for selecting the subgroup in the
"had an image" diagnostic further down, which is why that diagnostic is not an operating point.
2,599 `C#a -> C#b` pairs, which is **2.95% of view A's vertices**.
Among those 2,599, view A holds 2,756 internal edges and 1,288 of them recur in view B — a
**46.7% edge overlap**. So the structure the attack needs does partly recur; what does not is
presence: 97% of view A has no image in view B at all.

## The independent-seed path, tried first, yielded nothing

`ns_bitcoin.unique_entity_seeds` admits a seed only when an independently detected **entity name**
resolves to exactly one vertex in each view. Three of `decluster/entities.py`'s name-emitting
detectors were run over both windows (`detect_bitmex`, `detect_satoshidice`, `detect_mining_pool`).
The other two cannot fire on this export at all, and that is a schema fact, not an omission:
`detect_bip47_notification` reads an OP_RETURN scriptPubKey and `detect_dust_fanout` reads output
values, while every `vout` record here carries exactly one field, `scriptpubkey_address`. The
behaviour proxies (`detect_consolidation`, `detect_batching`) are excluded by kind rather than by
schema — they name a pattern, not an entity, so they cannot supply a one-to-one cross-view label.

| | view A | view B |
|---|---|---|
| BitMEX vanity-prefix hits | 33 | 73 |
| SatoshiDice `1dice` hits | 5 | 12 |
| distinct vertices labelled | 23 | 47 |
| entities unambiguous on **both** sides | **0** | |

The mining-pool detector cannot fire at all: it reads the coinbase scriptSig tag, which this
address-only export does not carry. Neither surviving detector names a single vertex per view — a
service's deposit addresses land in many clusters — so **zero** independent seeds were admitted,
and zero of them would have been gradeable. The seam refuses to pair an ambiguous label by degree,
which is exactly what stops the grading map from leaking in through the back door. The independent
attack is therefore **not identifiable on these views with the labels this export supports**, and
everything below is seed-assisted. That qualifier is the whole claim: with coinbase scriptSig tags
or a populated `catalog/entities.ndjson` the seed set might be non-empty, and this run says nothing
about that case.

## Seed-assisted sweep

`sweep_bitcoin_views`, seeds drawn uniformly (not by degree) from the withheld correspondence.
`theta` is part of the reported configuration: both a lowered value (0.5) and the module's default
(1.5, `decluster/baselines/narayanan_shmatikov.py:132`) are reported for every seed fraction, in
both cases whether or not anything propagated.

| seed frac | seeds | theta | rounds | declared | of those, had an image | correct | precision | precision where an image exists† | held-out | coverage |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5% | 130 | 0.5 | 9 | 248 | 17 | 2 | 0.81% | 11.8% | 2,469 | 0.081% |
| 5% | 130 | 1.5 | 9 | 246 | 16 | 1 | 0.41% | 6.3% | 2,469 | 0.041% |
| 10% | 260 | 0.5 | 8 | 450 | 32 | 3 | 0.67% | 9.4% | 2,339 | 0.128% |
| 10% | 260 | 1.5 | 8 | 448 | 31 | 2 | 0.45% | 6.5% | 2,339 | 0.086% |
| 25% | 650 | 0.5 | 10 | 779 | 49 | 10 | 1.28% | 20.4% | 1,949 | 0.513% |
| 25% | 650 | 1.5 | 10 | 774 | 47 | 9 | 1.16% | 19.1% | 1,949 | 0.462% |

† **Not an operating point.** That subgroup is selected by membership in the withheld
correspondence. The attacker cannot tell which of its 779 declarations are among the 49, so no
threshold available to it reaches 20.4%; the column says where the signal is, not what the attack
achieves. The attack's precision is the column to its left.

`results/artifacts/ns-bitcoin-v1.json` carries the full accepted-per-round series for the attack **and** the
shuffled control in every one of the six configurations; only the round *count* is tabulated here.

Propagation does spread — 8 to 10 rounds, front-loaded (at 25%/0.5: 410 accepted in round one,
then 207, 91, 34, ...). The headline is therefore **not** "nothing propagated". It is that almost
everything it propagated was wrong.

## Controls

| control | 5%/0.5 | 5%/1.5 | 10%/0.5 | 10%/1.5 | 25%/0.5 | 25%/1.5 |
|---|---:|---:|---:|---:|---:|---:|
| shuffled-seed: declared | 199 | 199 | 351 | 351 | 517 | 517 |
| shuffled-seed: **correct** | 0 | 0 | 0 | 0 | 0 | 0 |
| shuffled-seed: seeds left in place | 0 | 0 | 0 | 0 | 2 | 2 |
| seed-only: declared | 0 | 0 | 0 | 0 | 0 | 0 |
| paired discordant (attack / shuffled) | 2 / 0 | 1 / 0 | 3 / 0 | 2 / 0 | 10 / 0 | 9 / 0 |
| `separable` p | 0.500 | 1.000 | 0.250 | 0.500 | **0.0020** | **0.0039**|
| direction verdict | none | none | none | none | **attack** | **attack** |

The **shuffled-seed control recovers nothing in any configuration**, while propagating on a
similar scale (199-517 declarations). So the attack's correct matches are not an artifact of
seed positions. The **seed-only control declares 0** everywhere, so no number above is a seed
count in disguise.

The direction test is `decluster.reproducibility.separable` on the paired discordant counts, with
the pre-registered effect `min_correct_gain = 1` — the direction under test is "the attack recovers
at least one correspondence the shuffled-seed control does not", a **direction claim only**, which
says nothing about precision. At 5% and 10% seeding the sign favours the attack every time but the
discordant counts (1-3) are too small for a two-sided sign test to clear 0.05: **measured, not
separable** (state 5 of `results/REPRODUCIBILITY.md`). At 25% seeding it separates, p = 0.002 and
p = 0.004; six configurations were tested and these two clear Bonferroni at 0.05/6 = 0.0083, so the
conclusion survives the multiplicity.

**One assumption is worth stating rather than leaving in the arithmetic.** The sign test treats the
10 discordant vertices as independent exchangeable trials. Propagation is a cascade — round one
accepts 410 matches and every later round is conditioned on them — so one correct early match can
produce several correlated wins, and the effective number of independent trials is at most 10 and
plausibly fewer. The p-value is computed exactly as `separable` specifies and the *direction* is
sound (the control recovered nothing at all, in any configuration); its precise magnitude is not,
which is why the finding is stated as "beats the control" rather than as a calibrated confidence.

## The two failure modes, separated

Precision of ~1% invites the reading "the algorithm guesses". The `declared_with_an_image` column
says otherwise, and the split matters:

- **Most declarations are on vertices that have no image at all.** At 25%/0.5, 779 declarations,
  of which **730 were on vertices view B does not contain**. Those cannot be right. The 2009
  algorithm has no abstention for "this vertex is not in the other graph" — its own setting was two
  heavily overlapping views of one social graph — and on two disjoint observation windows 97% of a
  view is in that class.
- **Where an image does exist, the attack is doing real work.** 10 of 49 (20.4%) at 25%/0.5;
  9 of 47 (19.1%) at theta 1.5, against a shuffled control that declared on 22 vertices with
  images and got **0** of them. That comparison is the whole argument, and it is like-for-like.
  Again: this subgroup is chosen using the withheld correspondence, so 20.4% is a statement about
  where the signal lives, not a precision the attacker can operate at.

So the honest statement of the mechanism is: on real Bitcoin views the eccentricity test does carry
some real signal about *which* vertex a straddling pseudonym is, and carries essentially none about
*whether* a pseudonym straddles at all. Overall precision is dominated by the second.

## What this establishes, and what it does not

- **Does**: the faithful 2009 algorithm runs at real scale (88k x 104k vertices, about five
  minutes for the whole six-configuration sweep) and, handed a quarter of the correspondence,
  recovers 0.5% of the held-out remainder at 1.2% precision, beating a shuffled-seed control that
  recovers none in any configuration (p = 0.002, subject to the cascade-dependence caveat above).
- **Does not**: any independent de-anonymization claim. The seeds are grading information. With
  the independently observable entity labels this export supports, the seed set is **empty** and
  the attack cannot start — which is itself the more consequential finding for a real adversary
  than any row of the sweep.
- **Does not**: any claim about seed fractions between 25% and 100%, other windows, other epochs,
  or a clustering built with the amount and fingerprint channels this export cannot supply.

## Limits

- **One boundary, one epoch pair.** Six configurations over a single window pair. The coverage
  trend in seed fraction (0.08% -> 0.13% -> 0.51%) has a rising numerator *and* a falling
  denominator, because seeding more of the correspondence leaves less of it held out: it is
  2/2,469, then 3/2,339, then 10/1,949. Read the numerators alongside it. Three points, one
  boundary.
- **theta barely matters here.** 0.5 and 1.5 differ by one or two matches. The eccentricity
  threshold is not the binding constraint; presence in both views is.
- **The 20.4% figure conditions on information the attacker does not have.** It is measured on
  the declarations that landed on a vertex with an image, a subgroup selected from the withheld
  correspondence. There is no thresholding, ranking or abstention rule available to the attacker
  that isolates that subgroup, so the figure cannot be turned into an operating point and must not
  be quoted as this attack's precision.
- **The three seed sets are not nested.** `random.sample` changes algorithm at k = 650, so the 25%
  set shares only 251 of the 10% set's 260 seeds. The seed-fraction series is three draws, not a
  superset chain.
- **`split_frac = 1.0`.** Every straddling cluster is split, which maximises the correspondence
  population. A partial split would leave some straddlers un-pseudonymised and is not measured.
- **Uniform seed sampling.** Seeding the highest-degree correspondences instead would seed exactly
  the vertices propagation finds easiest and report the resulting spread as reach; that is why the
  sampling is uniform, and it means these numbers are not the best case a seed-choosing adversary
  could arrange.
- **Address-only export.** No coinbase tags (so no mining-pool labels), no values, no script types.
  The absent independent-seed path is a property of this export as much as of the chain.
- **No fix to `decluster/views.py` or `decluster/baselines/narayanan_shmatikov.py` was needed.**
  Both ran against real data unmodified; nothing in this run exposed a bug in either.

## Reproducibility / provenance

Manifest: `results/manifests/RESULTS-ns-bitcoin.json`, written by
`decluster.reproducibility.write_manifest` over `data/epochs_2016_weekly/*.ndjson.gz` (5 files,
1,024,227,001 bytes, recorded as a byte digest) with two kinds of invariant, because only one kind
is cheap to re-derive:

- **Recomputed and asserted** by `tests/test_ns_bitcoin.py::test_manifest_invariants_are_recomputed_and_match_results_ns_bitcoin`
  (2.4 s, skips with a named message when `data/epochs_2016_weekly/` is absent): the run
  configuration — `left_path`, `right_path`, `boundary` (392,112), `blocks` (120), `min_degree`
  (2), `split_frac` (1.0), `seed_fractions`, `thetas`, `rng_seed` — re-derived from the driver's
  own argparse defaults, and the two window transaction counts (133,576 and 157,724) read straight
  off the compressed epochs. The failure this closes is the one a digest cannot see: change a
  `--min-degree` or `--blocks` default and the epoch bytes are untouched, so the digest still
  matches while every published population number detaches from the code that produced it. That
  test now fails loudly instead.
- **Identity-only, not checked**: the contracted populations — vertices and edges per view
  (88,066/163,567 and 104,328/189,919), correspondence size (2,599), its internal and recurring
  edge counts (2,756 and 1,288) and their ratio (0.467344), the independent entity-seed count (0),
  and the seed-set sizes swept (130, 260, 650). Recomputing these means rebuilding two
  100k-vertex views over 291,300 transactions, which is minutes, not seconds, and so belongs in
  the driver rather than the suite. They are pinned by the recomputed configuration above plus the
  source digest, which is weaker than a recomputation and is stated here as such.

`tests/test_results_manifests.py` additionally checks the source digest on every run and reports
`identity-only` there, which is the policy's intended loud skip, not a pass.

Mechanism tests: `tests/test_ns_bitcoin.py` (seed admission, sampled-seed provenance and
reproducibility, the sweep grid, the paired separability verdict including the case where a real
advantage is too small to separate, the declaration split above, and view construction on a tiny
fixture) and `tests/test_ns_social_baseline.py` for the algorithm itself. Per
`results/REPRODUCIBILITY.md`, the numbers in this document are a **state 2** data-run over
unversioned data; the direction claim at 5% and 10% seeding is **state 5**, measured and not
separable, and at 25% seeding it clears all three gates of `separable`.

Reproduce: `.venv/bin/python examples/ns_bitcoin_views.py` (defaults are the canonical run:
`--blocks 120 --min-degree 2 --split-frac 1.0 --fractions 0.05 0.10 0.25 --thetas 0.5 1.5
--seed 7 --out results/ns-bitcoin.json`), which rewrites the frozen historical report a test holds
the canonical run against. Single process, peak RSS
about 1 GB; 283 s and 345 s on two runs of the identical command, which reproduced every number in
this document exactly.
