# Gap #1 — amount / subtransaction inference (the primary signal)

Reproduce: `python3 examples/subtx_demo.py`. Guarded by `tests/test_gap1.py`.

Closes the top audit gap: the amount-based inference that is *the main driver of
inferences* — "the fingerprinting is the cherry on top.

## The real merged transaction `931d6627`
| | value (sats) |
|---|---|
| input 0 — sender `91106666` | 2000 |
| input 1 — Cake receiver `0a568e3a` | 5750 |
| output 0 | 791 |
| output 1 | 6750 |
| fee | 209 |

## Amount inference (no fingerprints)
In a 2-in/2-out tx the per-owner balance is automatic, so the discriminator is the
**roundness** of the implied payment (`receiver_output − receiver_input`). Two partitions
survive `payment > 0`:

| receiver | payment | roundness |
|---|---|---|
| **in1 (Cake 5750) → out1 (6750)** | **1000** | **3** ✓ |
| in0 (sender 2000) → out1 (6750) | 4750 | 1 |

`ambiguity_bits = log2(2) = 1.0`. Roundness picks **payment = 1000** → the most-likely
partition:

- **REFUSE** `91106666` (sender) ↔ `0a568e3a` (Cake): the amount says the two inputs are
  **different owners** — re-partitioning the merged transaction *before any fingerprint*.
- **LINK** Cake `0a568e3a → 931d6627:out1`; sender `91106666 → 931d6627:out0`.

This is exactly the amount move: subtract the receiver's contributed input from its
output → a low-hanging round payment (1000). The "number of plausible partitions is a lot
lower than we think": here it is **1 bit**, and roundness resolves it.

## Two independent signals agree
| signal | verdict on sender↔Cake |
|---|---|
| **amount** (this result) | REFUSE, payment 1000, 1 bit ambiguity |
| **fingerprint** (WP4, `results/RESULTS-wp4.md`) | REFUSE, −3.1 bits (`max_ffffffff` vs `seq_0x01`) |

The amount is the primary structure (the cake); the fingerprint confirms (the cherry).
On this merged transaction they agree on the same re-partition.

## Honest caveats
- **Roundness is a prior, not proof.** A market-price payment can be non-round; the score
  is a likelihood weight, and `ambiguity_bits` reports honestly when amount does not
  disambiguate (here it is 1 bit, not 0).
- **2-in/2-out only.** General n-party subtransaction matching is deferred; other shapes
  return a scope guard (no silent wrong answer).
- **Agreement ≠ independence.** We observe amount and fingerprint agree on `931d6627`; we
  do not claim the two signals are statistically independent.
- **v1 assigns the whole fee to the sender** (typical merged transaction); a receiver fee share is a
  parameter left at 0.

`partition_signal(tx)` is the integration-ready output; wiring it into the combiner as a
structural weight (so amount and fingerprint fuse) is a documented follow-up.
