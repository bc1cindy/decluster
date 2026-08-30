# The sparse signal lives in ancestry, not in graph topology

**Why this reconciles the whole session.** The social-graph matching attack failed
(`RESULTS-view-match-2026.md`) and the pseudonym graph turned out not to be a social network
(`RESULTS-graph-shape.md`). But the framework's claim is specific: "cluster features, both
statistical and **more importantly structural**, are very likely to be unique." Structural
here means ancestry / deep features. This measures whether *that* space — not the graph
topology, not the statistical fingerprints — is sparse in the sparse-dataset attack's own
sense, which is the precondition the authors define as decisive.

**Method.** Ancestry signatures (`ancestry.absorber_distribution`, the provenance
distribution over ancestral origins) for a random 1 000 coins from the `.cache/`, which
carries real ancestry depth. Nearest-neighbour cosine similarity, survival curve, exactly
as `RESULTS-def1-sparsity.md` did for the statistical space. `decluster/def1_sparsity.py`
over `decluster/ancestry.py` signatures.

## Result

Signatures: median **4 797 dimensions** (max 11 511) — high-dimensional, as the attack
requires.

| epsilon | ancestry (deep features) | statistical (fingerprints) |
|---:|---:|---:|
| 0.5 | **0.331** | 1.000 |
| 0.9 | 0.179 | 0.981 |
| 0.99 | 0.165 | 0.889 |
| median top-sim | **0.200** | 1.000 |

## Reading

**The ancestry feature space is sparse; the statistical one is not.** Two thirds of coins
have no ancestry near-twin above similarity 0.5, and the median coin's closest match is only
0.20 — the Netflix-like regime the sparse-dataset attack needs. The statistical fingerprint
space is the opposite, 89 % with a near-identical twin. The framework's exact claim — that
the *structural* features are the unique ones, "more importantly" than the statistical — is
confirmed on real data, by the authors' own operational definition of sparsity.

**This reconciles the social-graph negative rather than contradicting it.** There are two
distinct N-S attacks, and this data separates them cleanly:

- the **social-graph** attack (cit. 24) matches two graphs by neighbourhood topology. Its
  precondition is that the pseudonym graph be a social network, and it is not
  (`RESULTS-graph-shape.md`), so this attack fails — measured, across 2013 and 2026.
- the **sparse-dataset** attack (cit. 19–20) matches records by sparse feature-vector
  overlap. Its precondition is (epsilon, delta)-sparsity of the feature space, and the
  ancestry space *has* it. This attack is the one `propagate.py` already runs
  (re-identification 0.154 on a bounded cache sample).

So the session's social-graph negative was never "de-anonymisation is impossible on this
data." It was "the sparse signal is not in the graph topology." It is in ancestry, and the
matching attack that consumes ancestry (record linkage, not graph matching) is the one whose
precondition holds.

## The caveat that bounds this, and points at the definitive run

The signatures here use a **uniform** link oracle (each input equally likely to fund each
output), not the real subset-sum `dss_link_oracle`, and depth 4 with `max_nodes=60`, to fit
the per-coin cost. A uniform oracle makes signatures *coarser* than the real ones — the
subset-sum weights would discriminate more. So the direction of the bias is conservative:
the true ancestry space is at least this sparse, probably more. A result of "sparse" under
a coarse oracle is therefore strong. The definitive measurement uses the real dss oracle at
depth 6 over a contiguous slice, which is what the deep contiguous export unblocks — now the
clearly highest-value collection, because it sharpens the one space the framework calls most
important and this run shows is the sparse one.

## Scope

1 000 coins from an accreted cache (not a uniform chain sample), uniform oracle, depth 4.
The survival curve is a sampled estimate. It establishes the *sign* of the result — ancestry
is sparse where statistics are not — robustly; the precise delta values await the dss-oracle
run.
