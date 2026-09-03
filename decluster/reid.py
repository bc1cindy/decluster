"""Record-linkage de-anonymization stratified by sparsity (Narayanan-Shmatikov 2008,
Algorithm 1B). Records are coins; each coin's provenance signature is its rarity-weighted
distribution over ancestral origins.

The measurement ties the sparse-dataset attack's *precondition* to its *success*: coins are
stratified by their own nearest-neighbour cosine (sparse = no near twin, dense = has one),
and the same Algorithm 1B attack is run on each stratum. Reveal `m` of a target's ancestors
as auxiliary information, score every candidate by the rarity-weighted provenance overlap
(`ancestry.provenance_link`, the paper's `wt = 1/log2(support)` scoring), and accept a match
only when the top score clears the runner-up by the eccentricity gate
(`propagate.eccentricity`, phi = 1.5 as in Netflix). Sparsity is the stratifier, so no
same-owner labels are needed and the two measurements are internally consistent. Theorem 2
predicts sparse records de-anonymize and dense ones do not; this measures that gap directly,
reusing the same primitives as the rest of the engine."""

import random

from .ancestry import provenance_link
from .propagate import build_rarity, eccentricity
from .def1_sparsity import cosine


def top_similarity(coins, sigs, metric="cosine", rarity=None):
    """Each coin's highest similarity to any *other* coin: its sparsity coordinate. Low = no
    near twin = sparse (de-anonymizable); high = has a twin = dense (protected).

    `metric="provlink"` measures that similarity in the *same* space the attack scores in
    (rarity-weighted provenance overlap, normalised by the coin's self-overlap), so the
    (epsilon,delta) stratification and the de-anonymization are internally consistent — the
    metric-consistency the Netflix paper assumes. `cosine` (default) preserves the committed
    fixture."""
    if metric == "provlink":
        selfs = {a: provenance_link(sigs[a], sigs[a], rarity) for a in coins}
        top = {}
        for i, a in enumerate(coins):
            sa, best = sigs[a], 0.0
            for j, b in enumerate(coins):
                if i == j:
                    continue
                denom = (selfs[a] * selfs[b]) ** 0.5
                s = provenance_link(sa, sigs[b], rarity) / denom if denom else 0.0
                if s > best:
                    best = s
            top[a] = best
        return top
    top = {}
    for i, a in enumerate(coins):
        sa, best = sigs[a], 0.0
        for j, b in enumerate(coins):
            if i == j:
                continue
            s = cosine(sa, sigs[b])
            if s > best:
                best = s
                if best >= 0.999:
                    break
        top[a] = best
    return top


def stratify(coins, sigs, sparse_below=0.5, dense_atleast=0.9, metric="cosine", rarity=None):
    """Split coins into sparse and dense strata by their own top-similarity."""
    top = top_similarity(coins, sigs, metric=metric, rarity=rarity)
    sparse = [c for c in coins if top[c] < sparse_below]
    dense = [c for c in coins if top[c] >= dense_atleast]
    return sparse, dense, top


def reid_attack(subset, coins, sigs, rarity, m, phi=1.5, seed=0):
    """Algorithm 1B on one stratum. For each target reveal `m` random ancestors as aux, score
    every candidate by rarity-weighted provenance overlap, and accept the top score only when
    its eccentricity clears `phi`. Returns (declared, exact, total): matches declared, of those
    how many pinned the target coin exactly, and how many targets were attackable (support>=m)."""
    rng = random.Random(seed)
    declared = exact = total = 0
    for target in subset:
        supp = list(sigs[target])
        if len(supp) < m:
            continue
        aux = {a: sigs[target][a] for a in rng.sample(supp, m)}
        scores = [provenance_link(aux, sigs[c], rarity) for c in coins]
        if len(scores) < 2:
            continue
        total += 1
        best_i = max(range(len(scores)), key=scores.__getitem__)
        if eccentricity(scores) >= phi:
            declared += 1
            if coins[best_i] == target:
                exact += 1
    return declared, exact, total


def stratified_reid(coins, sigs, ms=(4, 8), phi=1.5, seed=0,
                    sparse_below=0.5, dense_atleast=0.9, metric="cosine"):
    """Full measurement: split into sparse/dense strata, run the Algorithm 1B attack on each
    for each aux size in `ms`. Returns {rows, n, n_sparse, n_dense}, where each row is
    {stratum, m, declared, exact, precision, declare_rate}. The scientific quantity is the
    gap between sparse and dense precision, not the absolute level."""
    rarity = build_rarity(sigs.values())
    sparse, dense, _ = stratify(coins, sigs, sparse_below, dense_atleast, metric=metric, rarity=rarity)
    rows = []
    for name, subset in (("sparse", sparse), ("dense", dense)):
        for m in ms:
            dec, exa, tot = reid_attack(subset, coins, sigs, rarity, m, phi, seed)
            rows.append({"stratum": name, "m": m, "declared": dec, "exact": exa,
                         "precision": exa / dec if dec else 0.0,
                         "declare_rate": dec / tot if tot else 0.0})
    return {"rows": rows, "n": len(coins), "n_sparse": len(sparse), "n_dense": len(dense)}
