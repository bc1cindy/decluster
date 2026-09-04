# Subtransaction de-mix diagnostic

Canonical run: `catalog/runs/subtx-demix-v1.json`.

The executable summary is `results/generated/subtx-demix-v1.md`; the complete
measurement is `results/artifacts/subtx-demix-v1.json`. The internal dataset
preserves 39 cache JSON files containing 36 transactions and three outspend
responses.

For JoinMarket transaction `0cb4870c…856bbf`, the amount identity recovers eight
of twelve inputs, with implied fees of 191, 413, 458, 559, 623, 636, 687 and 973
satoshis. This reproduces the mechanism, not participant identities: there are
no independent maker labels.

The historical specificity claim is not supported. Of 25 width-eligible
transactions in this CoinJoin-adjacent cache, 22 trigger the heuristic. The
cache has no labels establishing that those transactions are ordinary payments,
so this is neither a false-positive rate nor evidence of specificity. The six
historical Wasabi rounds are not preserved and their zero-recovery claim is not
reproduced.

The fee cap and most-common-output detector are local modeling choices. This is
attacker-side de-mix evidence, not CoinScore or a privacy certificate.
