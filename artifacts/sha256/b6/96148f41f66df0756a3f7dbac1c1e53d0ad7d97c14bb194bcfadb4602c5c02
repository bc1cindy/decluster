# Collaborative transaction observer-knowledge matrix

Generated from the canonical experiment artifact. Do not edit manually.

The same two-input/two-output observation is compatible with an ordinary transaction and four PayJoin protocol forms. This does not identify which protocol form occurred.

| form | participants | external on-chain facts | counterparty facts |
|---|---:|---|---|
| ordinary_two_input | 1 | input and output amounts; transaction shape and script-visible construction features; participant allocation is not observed; payment amount is not observed | not applicable |
| p2ep | 2 | input and output amounts; transaction shape and script-visible construction features; participant allocation is not observed; payment amount is not observed | own inputs and outputs; the only other party's remaining inputs and outputs by elimination; negotiated payment amount |
| bip79_bustapay | 2 | input and output amounts; transaction shape and script-visible construction features; participant allocation is not observed; payment amount is not observed | own inputs and outputs; the only other party's remaining inputs and outputs by elimination; negotiated payment amount |
| bip78_sync_payjoin | 2 | input and output amounts; transaction shape and script-visible construction features; participant allocation is not observed; payment amount is not observed | own inputs and outputs; the only other party's remaining inputs and outputs by elimination; negotiated payment amount |
| bip77_async_payjoin | 2 | input and output amounts; transaction shape and script-visible construction features; participant allocation is not observed; payment amount is not observed | own inputs and outputs; the only other party's remaining inputs and outputs by elimination; negotiated payment amount |
| many_senders_one_receiver | 4 | amounts and transaction shape; sender allocation is not observed | the receiver knows each negotiated payment and sender change; the receiver may not know which input belongs to which sender |
| many_senders_many_receivers | 6 | amounts and transaction shape; payment pairing is not observed | own subtransaction and negotiated payment; other pairings remain latent |
| net_settlement_with_cycles | latent | net on-chain balances; participant count may remain latent | own obligations and contributions; other parties' gross obligations remain latent |

The shared observation is inputs `[90, 60]` and outputs `[110, 40]`. Protocol transport, participant allocation and negotiated payments are not added to the external observer's on-chain knowledge.

All allocations and relationships in this fixture are supplied possible worlds. The result is not ownership attribution, a deployment-frequency measurement or a privacy score.
