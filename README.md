# decluster

An adversarial laboratory for testing **de-anonymization failure modes in Bitcoin
transactions**. It keeps construction fingerprints, amount models, graph structure,
attribution and provenance as distinct evidence channels, including explicit abstention and
cannot-link outcomes. Those channels are model-relative and do not establish true ownership or
a general privacy score.

Two coins spent in the same transaction are normally assumed to share an owner. Because the
evidence here is *signed*, the clustering can instead **keep them apart** when their
fingerprints and amounts say they belong to different owners — undoing the false link a
collaborative transaction deliberately plants (its whole purpose is to make an analyst merge
two people into one).

- **Fingerprints reveal which wallet built a transaction.** Every wallet leaves quirks in
  how it constructs a transaction — nSequence values, script types, signature grinding, and
  more. Do those quirks actually identify the wallet? Taking address reuse as the same-owner
  label (two transactions spending the same address are the same wallet), the measured
  fingerprint bits rank a *same-wallet* pair of transactions above a *random* pair **94.6%
  of the time** on the committed 600-transaction fixture (AUC 0.9459, the manifest-backed run)
  and **92.4%** on the preserved 22,112-transaction cache (AUC 0.9244). Shuffle the labels and
  both drop to ~0.50 (a coin flip) — so the separation is real signal, not an artifact. An
  earlier figure of 0.933 over a 166k-transaction cache is a historical record: that cache was
  not preserved and the number is not recomputable. Two caveats travel with these: the
  preserved cache is Taproot-era only (heights 800,000–965,220), and on that cache 0.024 of
  the AUC is the address-reuse label restating itself — dropping the five axes the shared
  input address fixes outright takes 0.9244 to 0.9003.

- **The shape of the payment graph provides another model-relative signal.** Independently of
  who-spent-with-whom, recurring counterparty structure can support linkage. The local
  common-neighbour experiment is not the seeded cross-view Narayanan–Shmatikov attack. Across five eras (2012–2024),
  payment-graph structure *alone* predicts whether two addresses share an owner, ranking
  same-owner pairs correctly **0.95–0.97 of the time at one hop on the clean eras**, and
  **0.97–1.00 across all five eras by four hops** (1.0 = perfect, 0.5 = chance; the churny
  2013 slice starts near chance at one hop and needs the deeper hops). That is a *pairwise
  ranking* score, and it is the premise the attack needs rather than the attack: run to
  completion on two real Bitcoin views, the faithful 2009 propagation kernel reaches
  **0.41%–1.28% precision**, against a shuffled-seed control that gets nothing right
  (`results/RESULTS-ns-bitcoin.md`).

- **It survives a transaction built to fool it.** On a real transaction deliberately
  constructed to merge two owners into one (the false link from above), the method keeps
  them apart: the amount structure alone re-partitions them into the correct two owners, and
  the fingerprints independently agree — recovering the answer that a merge-only clustering
  gets wrong.

## Layout

**The package.** `decluster/` holds the measurement half. Modules are named for the evidence channel
they carry — `extractors`/`library`/`combiner` for construction fingerprints, `subsetsum`/`counting`/
`subtransaction` for amounts, `ancestry`/`provenance`/`intersect` for provenance, `views`/
`view_partition`/`contraction` for the coin graph — and they converge on two objects that travel in
opposite directions across the partition lattice: `cluster.cluster_refined` ascends, declining a
co-spend the merge-only heuristic would take, and `declustering.decluster` descends, cutting a
partition it did not build. `decluster/baselines/` reimplements published algorithms against their papers,
`decluster/experiments/` holds one module per canonical run, and `decluster/adaptations/` holds the pieces that are
named adaptations rather than reproductions.

**The evidence chain.** Every published number travels the same path, and each step is checkable:

```
catalog/datasets/   the data, pinned by digest
        ↓
decluster/experiments/   one module per run
        ↓
catalog/runs/   the manifest: command, parameters, environment, claim ids, verification
        ↓
results/artifacts/   the machine-written result
        ↓
results/generated/   the document rendered from it, never edited by hand
        ↓
releases/   the evidence bundle, listing every blob by name, size and digest
        ↓
artifacts/sha256/   the content-addressed store holding those bytes
```

`reproduction/` carries one environment and lockfile per bundle, and `sources/` a deterministic
archive of the code at the revision a run names. `decluster-bundle sync` keeps tree, index and store
in step; a gate fails if they drift. A run's `verify` recomputes its artifact and compares it byte
for byte.

**The prose.** `PAPER.md` is the manuscript. `results/` holds both halves of the record: documents
generated from artifacts, and hand-written `RESULTS-*.md` reports that predate the chain.
`results/REPRODUCIBILITY.md` files every one of them under an evidence state, and each document
carries a footer naming its state or saying plainly that none has been assigned.

**The rest.** `bigquery/` holds the extraction recipes, including the ones for collections the
policy names as still missing. `catalog/ctp-claims.json` and `ctp-sources.json` bind each claim to
the literature and to the code that implements it. `tests/` is written as gates rather than
coverage: each file pins a property that has broken once, and says which in its docstring.

Installable (`pip install -e .`), so a protocol-specific client model can consume these primitives
from above without this repository knowing the protocol exists.

Reproducibility is tracked per result. Every canonical run is bitwise reproducible from the committed store; the exact-oracle audit was the first, and bootstrapping any bundle looks the same:

```console
decluster-bundle --index releases/exact-oracle-evidence-v1.bundle.json \
  --store artifacts --root /tmp/decluster-bundle bootstrap
decluster-bundle --index releases/exact-oracle-evidence-v1.bundle.json \
  --root /tmp/decluster-bundle --work /tmp/decluster-run reproduce
```

That environment currently requires CPython 3.13 on macOS arm64. The committed content-addressed
store makes local cold-start execution possible. Public bootstrap remains pending until every blob
has a canonical HTTPS location and an independent mirror. Other results retain the guarantees and
limitations declared in `results/REPRODUCIBILITY.md` and their manifests.

MIT. See `LICENSE`.
