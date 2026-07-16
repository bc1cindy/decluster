# Change-id validation — validating the ordering axis (M&N labels + fingerprint tests)

Slice: `bigquery/slice.sql`, 1 day = 2024-06-01 (blocks 845982–846122, 739,889 txs).
Same-owner change labels: the change output revealed by multi-input **cluster membership** (M&N),
then filtered by M&N §2.2 (`build_gt_slice_mn`) — **fresh change** (change address appears as an
output only in T, an in-slice reuse proxy for M&N's "change already known at creation") and the
**>10% two-change cluster** exclusion.

**Raw labels: 1045 → n = 578** (467 dropped as in-slice reused-change; 0 by the two-change rule).
`M&N supercluster / tag-collapse removal (Mt.Gox) needs whole-chain tags and is NOT applied.`

## The valid result: per-axis change prediction (M&N Table 4 style; bootstrap B=2000)

Each axis votes "change = the output whose onward-spending tx **agrees with T on that axis**" — a
construction-fingerprint agreement between T and its output's spender, **disjoint** from the
address-graph label. `coverage` = fraction of labels where the axis fires (else it abstains);
`prec.` = precision when it fires (TPR / coverage).

| predictor | TPR [95% CI] | FPR | coverage | prec. |
|---|---|---|---|---|
| input_order | 0.320 [0.280, 0.358] | 0.066 | 0.386 | 0.83 |
| output_order | 0.436 [0.396, 0.474] | 0.048 | 0.484 | 0.90 |
| nsequence | 0.768 [0.734, 0.803] | 0.007 | 0.775 | 0.99 |
| version | 0.779 [0.744, 0.811] | 0.000 | 0.779 | 1.00 |
| change_index (round-number baseline) | 0.486 [0.446, 0.524] | 0.080 | 0.566 | 0.86 |

Combined tx-level pre↔post **AUC = 0.759 [0.716, 0.802]** vs shuffle-null ≈ 0.50 [0.44, 0.56] — the
change's onward-spend shares T's construction fingerprint more than the payment's does (a genuine,
label-disjoint signal; the shuffle control randomizes the pos/neg direction and collapses to ~0.5).

*FPR/precision caveat:* the label requires the change to be spent in-window, so on this slice the
change is spent 577/578 times but the payment only 226/578. A per-axis *false* vote is only possible
when the payment is spent, which mechanically depresses FPR and inflates precision for the high-
coverage axes (version/nSequence) — another face of the fast-wallet skew. The combined AUC is immune
(it uses only the 225 both-spent pairs).

### Reading (coverage-aware)

- **The ordering axis validates as a real but LOW-COVERAGE change signal.** `input_order` fires on
  only 39% of labels (vs 57% baseline, 78% version) and, when it fires, its precision (0.83) is
  about the round-number baseline (0.86). `output_order` fires on 48% at precision 0.90. So ordering
  resolves **fewer** cases, not less accurately — its low TPR is mostly low coverage, not low
  precision. This is the honest answer to "validating the ordering": as a change predictor it is
  real but low-coverage and no better than the round-number baseline in precision.
- **`nsequence` / `version` are the strong single tells** — near-perfect precision at high coverage:
  same-owner onward-spends reuse the wallet's sequence/version ~77–78% of the time.
- The fresh-change filter removed ~45% of raw labels (an **in-slice** reuse proxy for M&N's
  reused-change removal — not identical to M&N's whole-chain filter, and this share is slice-local,
  not comparable to M&N's 28.4%).

## The circular non-result: cluster `findNext` (reported ONLY as a circularity demonstration)

We also implemented Kappos's cluster-level `findNext` (change = the output at the cluster's `changeC`
index whose onward-spending tx's features are in the cluster's `TFC` set). **Against an M&N co-spend
label this is circular and is NOT evidence for any fingerprint:**

- The change output's onward-spender is, by construction, the co-spend **reveal** tx — a cluster
  member. Verified on this slice: the change spender is a cluster member **576/578**; the payment
  spender is a member **0/226**. So `features ∈ cluster TFC` is trivially true for the change, and
  the check collapses to *cluster membership = the label itself*.
- Proof: **nulling the entire construction fingerprint** (`tx_features → constant`) still gives
  **TPR 0.664** — so ~0.66 of the raw 0.862 is pure label structure with zero fingerprint content.
- `changeC` compounds it (it is the cluster-mates' change indices = the label); leave-one-out
  removes only T, never the reveal txs.

M&N's co-spend label and Kappos's co-spend-cluster `findNext` share the same signal, so `findNext`
cannot be validated against this label. The label-disjoint validation is the per-axis / tx-level
pre↔post test above (T vs its output's spender). `change_cluster.py` is kept for the method, but the
0.862 is a label-consistency upper bound, not a result.

## Scope

- Single day (n=578); labels skew to **fast-spending wallets** (only change spent within the window
  is revealed) over one-day clusters (thinner than full-history). Bootstrap quantifies within-day
  stability only; a multi-epoch replication is future work.
- Kappos's address-type check (AFC) is approximated from address prefixes (`_addr_type`), not the
  raw script type; on this 2024 slice it does not help (segwit/taproot homogeneity — Kappos's own
  caveat), so the per-axis fingerprint test, not AFC, carries the validation.
