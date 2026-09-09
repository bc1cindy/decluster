# Exact conservation versus explicit fee allocation

**Finding.** On a deterministic bounded sample of 300 ordinary multi-input transactions, all 300
pay a positive fee, so the exact-conservation baseline admits no mapping. The local fee-allocation
model admits the whole-transaction interpretation in all 300, but only **37** admit more than that
trivial single-block interpretation. The largest family has **192** mappings.

This is a measurement of `decluster.baselines.boltzmann`, not a claim of general parity with the
external Boltzmann tool. Separate reference tests now cover selected official vectors and modes.
The population measurements below remain specific to the local fee-allocation model.

## Protocol

Source: `data/amount-channel-812695-812831-v1.json`. Scan in file order and select the first 300 transactions satisfying all of:

- at least two inputs and one output;
- every input prevout and output has an integer value;
- at most eight input-plus-output coins, the declared exhaustive-enumeration bound.

For each selected transaction:

1. `exact_link_analysis` requires every participant block to balance exactly.
2. `fee_tolerant_link_analysis` permits a non-negative deficit in each block and sets the total
   tolerance to the transaction's observed fee, `sum(inputs) - sum(outputs)`.
3. Fee roundness is recorded independently as trailing decimal zeros. It does not admit, remove or
   weight a mapping.

| measurement | result |
|---|---:|
| selected transactions | 300 |
| positive-fee transactions | 300 |
| exact model with any mapping | 0 |
| fee-tolerant model with any mapping | 300 |
| fee-tolerant model with more than the all-coins mapping | 37 |
| maximum fee-tolerant mappings | 192 |
| round fees | 65 |
| round fee and nontrivial split | 10 |

The 300/300 fee-tolerant result is not evidence of de-mixing: the all-coins interpretation is
always admissible once the observed fee is allowed. The informative count here is 37/300, where at
least one participant split exists in addition to that trivial interpretation. Conversely, zero
exact mappings does not mean the transactions have no plausible ownership structure; it means an
exact zero-fee conservation rule cannot consume ordinary fee-paying transactions.

Roundness is deliberately not compared as a competing probability model. Ten transactions happen
to have both a round fee and a nontrivial split, but this run neither establishes association nor
uses roundness to rank the mappings.

## Reproducibility

Run:

```sh
.venv/bin/python examples/boltzmann_fee_audit.py --manifest
```

The complete per-transaction output is `results/artifacts/boltzmann-fee-audit-v1.json`, produced by
`catalog/runs/boltzmann-fee-audit-v1.json`. `results/boltzmann-fee-audit.json` is kept beside it as
the frozen historical report: `tests/test_boltzmann_fee_experiment.py` asserts the canonical run
still reproduces it exactly, which is a guard the canonical artifact cannot give itself.
The manifest fingerprints
`data/amount-channel-812695-812831-v1.json` and pins the configuration, population counts and outcomes
above. Tests recompute the report from that committed source rather than skipping when it is
absent. The official-tool parity cell remains open.
