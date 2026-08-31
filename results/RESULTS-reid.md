# Sparsity predicts de-anonymization: the record-linkage attack, stratified

**Why this closes the argument.** `RESULTS-ancestry-sparsity.md` measured that the ancestry
feature space is (epsilon, delta)-sparse: the precondition the sparse-dataset attack
(Narayanan-Shmatikov 2008, the Netflix de-anonymization) defines. That is the *means*. The
*end* the framework cares about is whether the attack then de-anonymizes. Their Theorem 2
states the link: if the space is sparse, a record is uniquely identified from a little
auxiliary information. This measures that link directly, on the same signatures where
sparsity was measured, using the same engine primitives.

**Reproducible.** The measurement is `decluster/reid.py`, exercised by `tests/test_reid.py`
against a frozen fixture of real ancestry signatures
(`tests/fixtures/reid_sigs.json.gz`). It is not a scratchpad run: the scoring is the engine's
own `ancestry.provenance_link`, the gate is `propagate.eccentricity`, and the numbers below
come out of `pytest`.

**Method (Algorithm 1B).** Records = coins; each coin's signature is its rarity-weighted
distribution over ancestral origins. For a target, reveal `m` of its ancestors as auxiliary
information (`aux`), score every candidate by the rarity-weighted provenance overlap
(`provenance_link`, `wt = 1/log2(support)`, the paper's scoring), and declare a match only
when the top score clears the runner-up by the eccentricity gate (phi = 1.5, the Netflix
value). Coins are **stratified by their own sparsity**: sparse = nearest-neighbour cosine
< 0.5 (no near-twin), dense = >= 0.9 (has a twin). Sparsity is the stratifier, so no
same-owner labels are needed and the two measurements are internally consistent.

**Data.** A frozen 200-coin fixture drawn from the depth-bounded `.cache/` (160 sparse,
40 dense; the dense stratum is over-sampled so the control is not a rounding error), each
coin carrying its own nearest-neighbour similarity as a frozen label. Uniform link oracle.

## Result

| stratum | m | attackable | declares | exact | precision | de-anon rate |
|---|---:|---:|---:|---:|---:|---:|
| sparse | 4 | 157 | 148 | 148 | 1.000 | 0.943 |
| sparse | 8 | 151 | 145 | 145 | 1.000 | 0.960 |
| dense | 4 | 40 | 9 | 9 | 1.000 | 0.225 |
| dense | 8 | 40 | 8 | 8 | 1.000 | 0.200 |

De-anon rate = exact hits / attackable. Chance baseline is 1/200 = 0.005.

## Reading

**Sparsity predicts de-anonymization, exactly as Theorem 2 says.** From four to eight
revealed ancestors, ~95% of *sparse* coins are pinned to the exact coin (190x the chance
rate), while *dense* coins reach ~0.20 (40x chance): a ~5x gap in the de-anon rate, measured
on one set of signatures. The attack works where the space is sparse and abstains where it
is not.

**The eccentricity gate is doing its job.** Every match it declares is exact (precision
1.000 in both strata): it never hands back a wrong coin. The strata differ in *how often it
declares*. On sparse coins the target stands clear of the field, the gate fires (declare rate
~0.95), and the pin is exact. On dense coins the near-twin ties the top two scores, the gate
falls below phi, and it **abstains** (declare rate ~0.20). This is the Definition-3 behaviour:
detect when there is no confident match rather than guess. Sharing ancestry is what preserves
a dense coin's pseudonymity, exactly the framework's own defence.

**More auxiliary information helps.** Sparse de-anon rate rises 0.943 -> 0.960 from m = 4 to
8, the direction Theorem 1 predicts (more known attributes, fewer false matches), and dense
declare rate falls 0.225 -> 0.200 as the added evidence makes the twin tie tighter.

## Scope, stated plainly

- The `.cache/` is an **accreted, non-representative** sample (dominated by two large
  clusters), not a uniform draw from the chain. This measures the sparsity->de-anon link on
  *these* signatures; it does not estimate a chain-wide de-anonymization rate.
- **Uniform link oracle**, not the real subset-sum dss oracle: conservative, as established
  in `RESULTS-ancestry-sparsity.md`. The real oracle sharpens signatures and would widen the
  gap, not narrow it. `reid.py` takes the scoring through `provenance_link`, so the dss
  oracle drops in without changing the harness.
- The revealed `m` ancestors are drawn at **random** from the target's support. A real
  counterparty (the Eve-Alice-Eve origin) can choose the *rare* ancestors and would do at
  least as well: the rates here are a floor for random aux, not a ceiling.
- 200-coin fixture; the required aux grows as log N (Theorem 1), so a chain-scale attack
  needs more known ancestors than shown here.

The representative measurement (a uniform chain sample at real depth with the dss oracle) is
the next collection, now motivated by a demonstrated link rather than an assumed one. It is
an API collection, not BigQuery. But the load-bearing claim is settled and reproducible here:
on sparse ancestry signatures, partial provenance knowledge de-anonymizes; on dense ones, the
attack correctly abstains.
