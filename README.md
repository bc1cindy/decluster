# decluster

Evidence-weighted **de-anonymization of Bitcoin transactions**. It reads how each
transaction was built (wallet fingerprints) and how its amounts partition (subtransaction
structure), scores every signal as **bits of evidence**, and clusters coins by owner.

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

- **The shape of the payment graph reveals owners too.** Independently of who-spent-with-whom,
  the *structure* of the graph (who pays whom) betrays common ownership — the same effect
  that de-anonymized social networks (Narayanan–Shmatikov). Across five eras (2012–2024),
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

- `decluster/` — the method: extractors, library, combiner, cluster (engine: `cluster_refined`), graph_deanon
- `PAPER.md` — the manuscript; `results/` — reproducible outputs; `catalog/`, `bigquery/`

Every number is reproducible. MIT — see `LICENSE`.
