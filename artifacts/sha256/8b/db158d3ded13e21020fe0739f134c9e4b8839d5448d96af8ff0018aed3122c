# N-S 2011 executable coverage

Generated from the canonical experiment artifact. Do not edit manually.

| component | status | limitation |
|---|---|---|
| `algorithm1_similarity` | `implemented` | — |
| `algorithm2_positive_weights` | `implemented` | — |
| `algorithm2_dummy_weights` | `mathematically_undefined` | dummy incident weights are zero but the published ratio divides by weights |
| `annealing` | `partial` | iteration budget, RNG and best-state return are explicit local controls |
| `two_stage_mapping` | `implemented` | — |
| `confidence_pruning` | `not_reproduced` | an implementation-complete pruning policy is not available |
| `accepted_mapping_correction` | `not_reproduced` | schedule and conflict resolution are not specified sufficiently |
| `algorithm3_cascade` | `implemented` | — |
| `learned_25_feature_model` | `not_reproduced` | the caller supplies an ML score; the published feature producer is absent |

Every non-implemented component is exercised through the refusal gate. The implemented components pass that gate, but the end-to-end paper pipeline remains unreproduced.

This deterministic contract does not reproduce the Flickr/Kaggle corpus, reported metrics, dummy-node convention, pruning policy, correction schedule, or learned model.
