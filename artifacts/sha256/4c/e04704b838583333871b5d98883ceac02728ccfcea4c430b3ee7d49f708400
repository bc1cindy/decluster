# The merged anchor's false edge under four axis sets

Generated from the canonical experiment artifact. Do not edit manually.

One edge — the sender's funding transaction against the Cake one, on anchor `931d6627`. The engine's refusal threshold is `link_above = 4.0`.

| axis set | axes | bits | verdict | past link_above |
|---|---:|---:|---|---|
| engine three axis | 3 | -3.16 | refuse | no |
| catalogued | 23 | +11.67 | link | yes |
| construction only | 18 | +4.91 | link | yes |
| decorrelated | 14 | +3.59 | link | no |

The catalogued model resurrects the edge at +11.67 bits, well past the threshold. Dropping one representative per correlated cluster leaves +3.59 — **8.07 bits of the score were copies of evidence already counted**, and what remains sits below the threshold, so the wide model's failure here is duplication rather than width.

Of the 22 axes that scored, 3 argue against the pairing (-10.82 bits between them) and 19 argue for it (+22.49); 1 abstain. The discriminating axes still refuse — they are outvoted by low-entropy policy axes that two ordinary wallets share, summed under a kernel that assumes they are independent.

This is one edge, chosen because the design decision was argued on it, and its same-owner reading is the paper's rather than an independent label. The library weights come from a population that was not preserved; `library-calibration-v1` measures how far they sit from the one that was.
