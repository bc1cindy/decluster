# Receiver-side change read-off in a many-senders PayJoin

Generated from the canonical experiment artifact. Do not edit manually.

The receiver knows its own coins and the payment negotiated with each sender, so a candidate change output must satisfy `input - payment == change`. One sender's constraint rarely settles it; the perfect matchings propagate it across senders.

| scenario | senders | matchings | distinct readings | unique reading | unanimous links |
|---|---:|---:|---:|---|---:|
| consolidating-receiver | 3 | 2 | 1 | yes | 1 |
| evenly-spaced-control | 3 | 2 | 2 | no | 0 |

Across 2 scenarios, 5 senders were ambiguous on their own constraint and propagation narrowed 2 of them; 1 scenario reached a single reading of the amounts.

Matchings and readings are counted separately on purpose. Two matchings that assign different output indices but the same amounts are one reading, and the reading is what the receiver learns — the consolidating scenario has two matchings and one reading.

Both scenarios are deterministic fixtures and the negotiated payments are supplied rather than inferred. An external observer holds neither those payments nor the receiver's own coins, so this is a counterparty capability. A unique reading of the amounts is not ownership attribution and is not a privacy score.
