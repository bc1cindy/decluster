# Conservation: forcing coinjoin outputs onto a known participant

`decluster/conservation.py`. If a set of outputs is worth more than every other
participant brought to the round, the excess had to come from the one participant
whose input we can name. No client model is involved — not the denomination
lattice, not the decomposer, not vsize, not a null. Arithmetic on what the
transaction shows.

The bound is a floor in one direction on purpose: output fees are ignored, which
understates what the others had to pay, so any real fee raises the count and never
lowers it.

## The chain

Six consecutive mainnet coinjoins in which one participant re-registers the
previous round's change. Every hop was confirmed by walking the spend forward, so
the participant's registered input is known at each round rather than assumed.

| round | txid | in / out | round total | participant | others | share |
|---|---|---|---|---|---|---|
| R1 | `f3ee6e61129b90b4` | 324 / 382 | 93.34360001 | 64.90373154 | 28.43986847 | 69.5% |
| R2 | `3bdac8ed822fc4cb` | 320 / 374 | 72.88854242 | 54.31783009 | 18.57071233 | 74.5% |
| R3 | `80f11c778a2f486f` | 454 / 502 | 90.00971062 | 47.12126860 | 42.88844202 | 52.4% |
| R4 | `af9fcf4d87ea2644` | 318 / 380 | 23.37154435 | 0.50853104 | 22.86301331 | 2.2% |
| R5 | `1780de3bc7f7c6ad` | 339 / 409 | 25.82011167 | 0.05377888 | 25.76633279 | 0.2% |
| R6 | `41846eaf5653706c` | 295 / 354 | 35.44835283 | 0.00590849 | 35.44244434 | 0.0% |

All amounts in BTC. R6's change is still unspent; the chain ends there.

## What conservation forces

Per denomination — the reading that names *which* outputs are forced:

| round | denomination | forced | present | margin |
|---|---|---|---|---|
| R1 | 54.31783009 | 1 | 1 | 25.87796162 |
| R2 | 47.12126860 | 1 | 1 | 28.55055627 |
| R3 | 7.74840978 | **2** | 7 | 3.60201666 |
| R4–R6 | — | 0 | — | — |

"Margin" is how much more the other participants would have needed for one further
output to be explicable without the known participant. It is the distance from the
conclusion to a boundary: at 3.6 BTC on the tightest row, no rounding and no
unmodelled fee can overturn it.

R1 and R2 force exactly the change outputs, which the forward walk had already
established independently. That is not new information — it is the method
agreeing with a separately-derived fact, which is the only validation available
here. **R3 is the result**: two of seven equal outputs, 15.49681956 BTC, forced by
arithmetic alone in a round the de-mix cannot touch.

## Where it stops working, and why

The inequality bites only when the participant is large relative to the round.
Above roughly half the round's input it forces; below that the others can always
cover. R4 through R6 force nothing at 2.2%, 0.2% and 0.0%, and neither do the six
rounds that later consumed the 7.74840978 BTC outputs, where the participant holds
7.75 BTC against rounds of 19.7 to 33.7 BTC.

This is a property of the argument, not of this participant. Fragmenting defeats
it. What exposed R1–R3 was entering with 64.9 BTC at once.

## Pooling: more satoshi, less identification

`forced_prefixes` reports the bound over growing sets of the largest output values.
R3:

| denominations | smallest in set | forced | ≥ coins | pool |
|---|---|---|---|---|
| 1 | 7.74840978 | 11.35042644 | 2 | 7 |
| 2 | 3.87420489 | 19.09883622 | 3 | 9 |
| 3 | 1.00000000 | 27.09883622 | 4 | 17 |
| 4 | 0.50853104 | 27.60736726 | 4 | 18 |

The second row is the only worthwhile extension: 7.75 BTC more forced for a pool
that grows from seven coins to nine. From the third row the pool roughly doubles
per step and identification dissolves.

The sweep converges on a trivial bound as the pool grows — take every output and
"forced" approaches the participant's own input, which says nothing. The function
returns the whole curve rather than its maximum for that reason.

## Reproduce

```python
from decluster.fetch import fetch_tx
from decluster.conservation import forced_in_round, forced_prefixes

tx = fetch_tx("80f11c778a2f486ffc55b4e8665a94971ae9c350ac53969e9efcbf90478cbf90")
forced_in_round(tx, 4712126860)   # [(774840978, 2, 7)]
forced_prefixes(tx, 4712126860)   # the curve above
```

## Relation to the amount channel as measured elsewhere

`RESULTS-subtx-demix.md` reports that the labelled dense coinjoins recover **0**
participants, and PAPER §9 reads that as those rounds being amount-private. Both
remain true of the de-mix, which looks for `input = mix + change − fee` and finds
no unique match in dense denomination tiers.

Conservation is a different argument in the same channel, and it is not silent
there. A round is amount-private *to the de-mix*; a participant who dominates the
round is separately exposed by conservation. The two do not overlap: the de-mix
partitions participants and abstains under ambiguity, while conservation ignores
the partition entirely and asks only what the others could afford.
