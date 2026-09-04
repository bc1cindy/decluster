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
  fingerprint bits rank a *same-wallet* pair of transactions above a *random* pair **93.3%
  of the time** (AUC 0.933) on 166k real mainnet transactions. Shuffle the labels and it
  drops to 0.50 (a coin flip) — so the 0.933 is real signal, not an artifact.

- **The shape of the payment graph provides another model-relative signal.** Independently of
  who-spent-with-whom, recurring counterparty structure can support linkage. The local
  common-neighbour experiment is not the seeded cross-view Narayanan–Shmatikov attack. Across five eras (2012–2024),
  payment-graph structure *alone* predicts whether two addresses share an owner, ranking
  same-owner pairs correctly **0.95–0.97 of the time at one hop on the clean eras**, and
  **0.97–1.00 across all five eras by four hops** (1.0 = perfect, 0.5 = chance; the churny
  2013 slice starts near chance at one hop and needs the deeper hops).

- **It survives a transaction built to fool it.** On a real transaction deliberately
  constructed to merge two owners into one (the false link from above), the method keeps
  them apart: the amount structure alone re-partitions them into the correct two owners, and
  the fingerprints independently agree — recovering the answer that a merge-only clustering
  gets wrong.

## Layout

- `decluster/` — the attacker (the measurement half that runs): extractors, library, combiner,
  cluster (engine: `cluster_refined`); `baselines/narayanan_shmatikov` contains the two-view 2009
  propagation scoring kernel, while `propagate`, `graph_deanon`, and `baselines/link_prediction`
  are separately named adaptations rather than N-S reproductions
- the construction/cost half (deferred — PAPER §9): `cost` (leak / amount-cut / topology leaf terms + the deferred `construction_cost`), `ancestry` (the absorber-model provenance target; feeds propagate), `report` (fuses the terms on a real tx), `subsetsum`/`coinjoin_demix` (the amount de-mix channel); consumes the `dense-subset-sum` engine (build: `maturin develop`); `cluster_refined` optionally refuses links when provenance and fingerprints diverge
- chain-analysis channels that select what to ask and read the answer, all outside the engine:
  `conservation` (what the other participants could not have funded — arithmetic on one transaction,
  no client model), `provenance` (which inputs descend from known transactions), `monitor` (watches
  tracked coins for the co-spend an intersection argument needs), `intersect` (the N-ary origin
  intersection, handed to `cluster_refined` to score rather than asserted)
- `PAPER.md` — the manuscript; `results/` — a mixture of canonical generated artifacts and
  explicitly inventoried historical reports; `catalog/` — claims, datasets and executable run
  manifests; `bigquery/` — versioned extraction recipes

Installable (`pip install -e .`), so a protocol-specific client model can consume these primitives
from above without this repository knowing the protocol exists.

Reproducibility is tracked per result. The exact-oracle audit is the first bitwise-reproducible run:

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
