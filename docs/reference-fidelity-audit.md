# Primary-source fidelity audit

Checked 2026-09-03 against the primary texts and reference implementation linked below. “Kernel”
means the defining calculation is executable; “reproduction” additionally requires the paper's
input construction, policy choices and expected output.

| Reference | Primary source | Local status | What remains |
|---|---|---|---|
| Fellegi–Sunter (1969) | [paper](https://nhis.ipums.org/nhis/resources/Fellegi69.pdf) | Kernel implemented: comparison vectors, conditional `m/u` log-likelihood weights, three-way decision and held-out evaluation. | The local Beta smoothing is an explicit estimation choice, not a paper result. Keep value-rarity scoring named separately. |
| Narayanan–Shmatikov sparse data (2008) | [paper](https://arxiv.org/pdf/cs/0610105) | Rarity-weighted record matching is an adapted application. | Do not call Bitcoin AUCs a reproduction of Netflix Algorithm 1B; its auxiliary-information model, `1/log |supp(i)|`, eccentricity and exponential score distribution form one contract. |
| Narayanan–Shmatikov social graphs (2009) | [paper](https://arxiv.org/pdf/0903.3276) | Directional, degree-normalized propagation score, eccentricity and reverse match are implemented and run on synthetic and Bitcoin views. | Seed clique discovery and revisiting/remapping accepted nodes are missing; Twitter/Flickr/LiveJournal results are not reproduced. The module is a propagation kernel, not the full attack. |
| Narayanan–Shi–Rubinstein link prediction (2011) | [paper](https://arxiv.org/pdf/1102.4374) | Algorithm 1's crawl-aware directed cosine, the published stage-1 thresholds (`k=4`, `theta=.5`, `delta=.2`), relaxed top-three stage-2 candidates (`k=3`, `theta=.5`), and Algorithm 3's deterministic/vote/ML cascade are executable. A smaller local adjacency-transfer experiment remains separately named. | Partial. Iterative scheduling/revisiting, confidence pruning between runs, simulated-annealing seed matching and the 25-feature random forest remain missing. The local common-neighbour experiment is not this algorithm. |
| Maurer–Neudecker–Florian (2017) | [paper](https://m.flrn.cc/academic/2017_CoinJoin.pdf) | Exact mappings and the paper's non-derived selection are executable; Figure 2 (`21,12,36,28 → 25,8,50,14`) is a regression fixture. | Reproduce the output-splitting experiments/figures if their empirical claim is needed. Fees are deliberately outside this model. |
| LaurentMT / Boltzmann | [metrics](https://gist.github.com/LaurentMT/e758767ca4038ac40aaf), [LPM](https://gist.github.com/LaurentMT/d361bca6dc52868573a2), [reference code](https://github.com/Samourai-Wallet/boltzmann) | A separate dependency-free port reproduces the official default `LINKABILITY` aggregate traversal, including P3-with-fees (28 combinations and `14/13/13` link counts) and asymmetric no-fee vectors. The older set-valued fee model remains separately named. | `PRECHECK`, `MERGE_INPUTS`, `MERGE_OUTPUTS`, `MERGE_FEES` and JoinMarket intrafees remain absent. They have distinct semantics, not aliases for the default traversal. |
| Goldfeder et al. (2018) | [paper](https://arxiv.org/pdf/1708.04748) | Algorithm 2's core is executable: join-only ancestry to `r`, address-cluster lift, intersection, unique-or-refuse. | JoinMarket detection, recursive clustering, 2015–2017 simulation and 21-purchase validation are not reproduced. `decluster/intersect.py` remains an adapted probabilistic pipeline, not Algorithm 2. |
| Kelen–Seres (2022) | [paper](https://arxiv.org/pdf/2211.04259) | Equation 1 nominal-value reverse transitions, absorbing probabilities and Shannon untraceability are implemented; Figure 2's `5:3:2 → .5:.3:.2` transition is pinned. | Expected steps, auxiliary source nodes, account stationary/temporal transforms and Tables 1–2 are missing. The published Bitcoin Table 1 requires its full chain interval, not the local depth-limited walk. |

## Consequences for the plan

1. Maurer's “paper cases” is no longer wholly blocked: the defining Figure 2 case and non-derived
   semantics are now tested. Its experimental output-splitting section remains separate work.
2. Goldfeder's abstract intersection cell is now an Algorithm 2 kernel, but the existing real-chain
   `intersect.py` measurement cannot be relabeled as the paper's reproduction.
3. Boltzmann's default aggregate-traversal multiplicity is now reproduced separately. The
   set-valued fee model still intentionally disagrees and must not be described as Boltzmann;
   parity for optional merge/precheck/intrafee modes remains open.
4. Kelen–Seres' core transition is faithful, but “Kelen–Seres complete” would be false without the
   graph transforms, expected absorption time and table reproduction.
5. The 2011 cell is partial: Algorithms 1 and 3 plus both published threshold policies are pinned,
   but their iterative driver, seed optimizer and learned-score producer remain open. Its actual
   composite is materially different from `baselines/link_prediction.py`.
