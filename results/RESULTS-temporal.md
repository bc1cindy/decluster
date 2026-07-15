# Cluster temporal fingerprint — when is a cluster active

Reproduce: `python3 tests/test_broadcast.py` (`test_cluster_temporal`). Functions in
`decluster/broadcast.py`: `tx_time`, `active_hours`, `schedule_distance`.

## Idea

Beyond *whether* a wallet sets nLocktime (the per-tx `locktime_vs_broadcast` axis), the
broadcast-time estimate aggregated over a whole cluster *could* give **when the cluster tends to
be active** — its hour-of-day schedule, i.e. a timezone signature — a candidate cluster-level
quasi-identifier complementary to the counterparty topology (`results/RESULTS-topology.md`).
This file defines the mechanism and then **tests that hypothesis on real data — where it does not
hold up** (see "a NULL under proper controls" below). It is reported here as a negative result.

## Mechanism

- `tx_time(tx)` — the best broadcast-time estimate: the tight-window midpoint when the
  feerate bound is tight, else the inclusion time (a coarser ~10-min-late proxy).
- `active_hours(times)` — a 24-bin UTC hour-of-day histogram: the cluster's schedule.
- `schedule_distance(a, b)` — total-variation distance between two normalized schedules
  (`0` = identical hours, `1` = disjoint).

## Demonstration (`test_cluster_temporal`)

Alice's cluster active ~03:00 UTC vs Bob's ~15:00 UTC → `schedule_distance = 1.0` (disjoint,
fully distinguishable); a schedule against itself → `0.0`. The mechanism separates clusters by
activity schedule.

## Real-data calibration — a NULL under proper controls

Same owner = address reuse (near-certain): for an input address reused ≥8 times over a **wide**
window, its txs' hour-of-day histogram is its schedule. We ask whether that schedule *identifies
the owner*. Harness: `calibrate_temporal` (`decluster/broadcast.py`), on a **30-day** export
(`bigquery/temporal.sql`, 2024-01) of **20 000** reused input addresses (≥8 txs each, median span
14.7 days, median 6 of 24 distinct hours touched). Reproduce:
`python3 -m decluster.broadcast temporal <export.json>`.

| test | same | cross | AUC |
|---|---:|---:|---:|
| baseline — random split-half | 0.401 | 0.865 | **0.923** |
| persistence — time-ordered split | 0.621 | 0.863 | **0.736** |
| persistence, ≥7-day span only | 0.733 | 0.803 | **0.596** |
| matched — negatives matched on active-hours count | 0.621 | 0.672 | **0.492** |

The headline **0.923 is an artifact of two confounds**, not an owner-identifying schedule:

1. **Random split-half tests concentration, not persistence.** The two halves are i.i.d. samples
   of one pooled distribution, so the distance is small whenever the address touches a *narrow
   band of hours* — regardless of which hours or whether the band persists. Splitting by **time**
   instead (does the schedule hold across the window?) drops the AUC to **0.736**, and to **0.596**
   on the ≥7-day subset.
2. **Negatives weren't matched on band width.** Most of the remaining separation is just
   "narrow band vs narrow band at different hours." Drawing negatives from addresses with the
   **same active-hours count** removes it: **AUC 0.492 — chance.**

So on reused-address data the hour-of-day schedule does **not** separate owners once concentration
is controlled for. A random-band synthetic (bands placed at arbitrary hours with no owner meaning)
reproduces the ~0.92 baseline, confirming the number measures "addresses have a narrow active-hours
band," not "the schedule identifies the owner." This joins the ~1-day slice (AUC 0.39, `sample.ndjson`)
as a **null**: the earlier 0.92 claim was confounded and is retracted.

**A cleaner owner labeling gives the same null.** To rule out "it's only the service-skewed
reused-address population," we re-ran on **co-spend entities** (`bigquery/temporal-cospend.sql`:
addresses spent together = one owner, tx count capped at 200 to drop mega-services) — closer to
individual, multi-address wallets. Same 30-day window, 20 000 entities: baseline 0.889, persistence
0.760, **matched 0.522** — still chance. The null is *structural* (the metric plus concentration),
not an artifact of picking service addresses.

## Honest limits

- **Not validated as an owner separator.** The mechanism (`active_hours`/`schedule_distance`) is
  well-defined and disjoint active hours are still weak evidence of *different* owners, but this
  data does not demonstrate a positive same-owner temporal fingerprint — a fair test lands at chance.
- The population is *reused-address* clusters (address reuse skews toward services, active ~24/7),
  which may under-show a timezone effect for individuals; isolating that needs a different ground
  truth and a persistence-based, band-matched test (as above).
- Uses the broadcast estimate, so it inherits its limit — coarser where the bound is loose.
