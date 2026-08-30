# Does declining to apply CIOH blindly change the 2026 picture?

**Why ask.** `RESULTS-contraction-2026.md` flagged its own clustering as a deliberate
simplification: naive common-input union-find is precisely the adversary the framework calls
incompetent, and its largest cluster, 30 304 addresses, was suspected of being a merge
artifact rather than one owner. This measures what a refusing clusterer actually changes.

**What was implemented.** Two refusal rules, both decidable from the spending transaction
alone, so both survive at slice scale:

- **coinjoin shape** — many inputs against many outputs is where co-spending stops implying
  common ownership, so no input merges with any other. This is the framework's own stated
  rule for the cautious adversary.
- **de-mix partition** — where `coinjoin_demix` resolves inputs to distinct participants,
  only same-participant inputs merge, and an input it cannot resolve merges with nobody.
  Returning the partition rather than per-pair verdicts is what keeps this linear.

**Data.** `slice_2026.ndjson`, 831 770 transactions, of which **141 452 (17.0 %) have two
or more distinct input addresses** and so present a CIOH merge decision at all.

## Result

| | fires on | share of multi-input txs |
|---|---:|---:|
| coinjoin shape (≥ 20 in and ≥ 20 out) | 409 | 0.29 % |
| de-mix partition | 58 | 0.04 % |
| **either** | **467** | **0.33 %** |

| clustering | addresses | clusters | five largest |
|---|---:|---:|---|
| naive | 633 933 | 55 850 | 30 304, 21 912, 15 216, 15 177, 11 556 |
| refusing | 605 463 | 55 515 | 30 304, 21 912, 15 216, 14 859, 11 556 |

Downstream, at seed 400:

| clustering | vertices | spanning | seedable | matched | correct | precision |
|---|---:|---:|---:|---:|---:|---:|
| naive | 395 547 | 33 033 | 5 132 | 145 | 83 | 0.572 |
| refusing | 411 376 | 33 114 | 5 167 | 139 | 81 | 0.583 |

## Reading

**The refusal is inert on this data.** It touches 0.33 % of the merge decisions, and
precision moves from 0.572 to 0.583, which at n ≈ 140 is noise. The distinction between the
blind adversary and the cautious one, which the framework treats as decisive, does not
separate them here.

**The mega-clusters are untouched.** 30 304 and 21 912 come out identical under both. They
are not built from coinjoin-shaped or de-mixable transactions; they are built from ordinary
multi-input consolidations that neither rule can see. So the earlier suspicion is now
narrower rather than confirmed: if that cluster is an artifact, it is one only the
fingerprint channel could expose.

**And that channel is unavailable for a reason worth naming precisely.** The fingerprint
refusal compares the *funding* transactions of two co-spent coins, not the transaction that
spends them. For a two-day slice those funders lie almost entirely outside it. The
limitation is data, not algorithm, and the requirement it implies is bounded and specific:
one hop back from every in-slice input. That is the concrete change a future export needs
in order to test the cautious adversary properly.

**One knob is doing a lot of the work and is not calibrated.** The coinjoin-shape rule fires
at twenty inputs *and* twenty outputs, which is strict; most collaborative transactions,
payjoins above all, look nothing like that. A looser threshold would refuse more, and
whether it should is an empirical question this does not answer. Loosening it without
evidence would trade one unexamined default for another.

## Scope

Two refusal channels of the engine's five. The roundness channel is deliberately excluded
rather than merely absent: it is gated on the fingerprint disagreeing, and used alone it
would refuse ordinary round payments. Provenance is out for the same reason as
fingerprints. Single slice, single month.
