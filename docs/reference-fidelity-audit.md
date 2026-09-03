# Primary-source fidelity audit

Checked 2026-09-03 against the primary texts and reference implementation linked below. “Kernel”
means the defining calculation is executable; “reproduction” additionally requires the paper's
input construction, policy choices and expected output.

| Reference | Primary source | Local status | What remains |
|---|---|---|---|
| Fellegi–Sunter (1969) | [paper](https://nhis.ipums.org/nhis/resources/Fellegi69.pdf) | Kernel implemented: comparison vectors, conditional `m/u` log-likelihood weights, three-way decision and held-out evaluation. | The local Beta smoothing is an explicit estimation choice, not a paper result. Keep value-rarity scoring named separately. |
| Narayanan–Shmatikov sparse data (2008) | [paper](https://arxiv.org/pdf/cs/0610105) | Rarity-weighted record matching is an adapted application. | Do not call Bitcoin AUCs a reproduction of Netflix Algorithm 1B; its auxiliary-information model, `1/log |supp(i)|`, eccentricity and exponential score distribution form one contract. |
| Narayanan–Shmatikov social graphs (2009) | [paper](https://arxiv.org/pdf/0903.3276) | Directional, degree-normalized propagation score, eccentricity and reverse match are implemented and run on synthetic and Bitcoin views. | Seed clique discovery and revisiting/remapping accepted nodes are missing; Twitter/Flickr/LiveJournal results are not reproduced. The module is a propagation kernel, not the full attack. |
| Narayanan–Shi–Rubinstein link prediction (2011) | [paper](https://arxiv.org/pdf/1102.4374) | Algorithm 1's crawl-aware directed cosine, both threshold policies, a reproducible two-stage driver with stage-1 feedback and non-feeding stage-2 candidates, Algorithm 3's deterministic/vote/ML cascade, and Algorithm 2's positive-weight distance plus swap/cooling annealer are executable. A smaller local adjacency-transfer experiment remains separately named. | Partial. The pseudocode's ratio is undefined for zero weights even though dummy incident weights are zero; the implementation refuses that case instead of inventing smoothing. Revisiting/correction, confidence pruning and the 25-feature random forest remain missing. |
| Maurer–Neudecker–Florian (2017) | [paper](https://m.flrn.cc/academic/2017_CoinJoin.pdf) | Exact mappings and the paper's non-derived selection are executable; Figure 2 (`21,12,36,28 → 25,8,50,14`) is a regression fixture. | Reproduce the output-splitting experiments/figures if their empirical claim is needed. Fees are deliberately outside this model. |
| LaurentMT / Boltzmann | [metrics](https://gist.github.com/LaurentMT/e758767ca4038ac40aaf), [LPM](https://gist.github.com/LaurentMT/d361bca6dc52868573a2), [reference code](https://github.com/Samourai-Wallet/boltzmann) | A separate dependency-free port reproduces default `LINKABILITY`, including fee multiplicity and asymmetric vectors. `MERGE_FEES` is also reproduced as a typed synthetic fee-output mode, including its output position and official P3 count/matrix. The older set-valued fee model remains separately named. | `PRECHECK`, `MERGE_INPUTS`, `MERGE_OUTPUTS` and JoinMarket intrafees remain absent. They have distinct semantics, not aliases for the default traversal. |
| Goldfeder et al. (2018) | [paper](https://arxiv.org/pdf/1708.04748) | Algorithm 2's core is executable: join-only ancestry to `r`, address-cluster lift, intersection, unique-or-refuse. | JoinMarket detection, recursive clustering, 2015–2017 simulation and 21-purchase validation are not reproduced. `decluster/intersect.py` remains an adapted probabilistic pipeline, not Algorithm 2. |
| Kelen–Seres (2022) | [paper](https://arxiv.org/pdf/2211.04259) | Equation 1 transitions, auxiliary-source materialization, absorption probabilities, Shannon untraceability, `t=N1` expected steps, and stationary/temporal account transforms are implemented. Figure 2's `5:3:2 → .5:.3:.2` transition is pinned. The temporal transform splits on receipts, carries prior balance and requires explicit pre-window balances. | Tables 1–2 are not reproduced. The published Bitcoin table requires its full chain interval, not a depth-limited walk. |

## Consequences for the plan

1. Maurer's “paper cases” is no longer wholly blocked: the defining Figure 2 case and non-derived
   semantics are now tested. Its experimental output-splitting section remains separate work.
2. Goldfeder's abstract intersection cell is now an Algorithm 2 kernel, but the existing real-chain
   `intersect.py` measurement cannot be relabeled as the paper's reproduction.
3. Boltzmann's default aggregate-traversal multiplicity is now reproduced separately. The
   set-valued fee model still intentionally disagrees and must not be described as Boltzmann;
   parity for owner-merge/precheck/intrafee modes remains open.
4. Kelen–Seres' UTXO transition, explicit source nodes, absorption distribution, expected absorption
   time and account/time transforms are executable. “Kelen–Seres complete” remains false without
   the paper's data-scale table reproduction.
5. The 2011 cell is partial: Algorithms 1 and 3, both threshold policies, and Algorithm 2 on its
   mathematically defined positive-weight domain are pinned. Dummy-node zero semantics, the
   revisiting/pruning policies and learned-score producer remain open. Its actual composite is
   materially different from `baselines/link_prediction.py`.
