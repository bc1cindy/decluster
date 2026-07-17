"""Bayesian (Gibbs) vs Fellegi-Sunter comparison on decluster's per-axis evidence. On the same reuse
pairs, scores three ways under the shared per-field likelihood — F-S(0.95), F-S(EM), Bayesian(integrated
m) — and reports AUC (tie control), ECE (calibration), the per-axis m posterior vs EM/oracle/0.95, and a
cluster-level entity-count band in two regimes: clear address-reuse structure (band collapses, Bayesian =
F-S) and ambiguous borderline structure (a genuine band — the uncertainty a point estimate hides). Offline.
Run from repo root: python3 examples/bayes_vs_fs.py. See results/RESULTS-bayes-vs-fs.md."""
import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _auc_split(probs, n_pos):
    from decluster.graph_deanon import auc
    return auc(probs[:n_pos], probs[n_pos:], 0)


def _entity_counts(A, mask, u, m_samples, lam, node_pairs, n_nodes, seed, cap=200):
    """For a subsample of m draws, sample edges ~ pair P(match) and count connected components."""
    from decluster.fs_bayes import pair_probs
    from decluster.unionfind import UF
    rng = random.Random(seed)
    counts = []
    for m in m_samples[:cap]:
        pm = pair_probs(A, mask, m, u, lam)
        uf = UF(range(n_nodes))
        for (i, j), p in zip(node_pairs, pm):
            if rng.random() < p:
                uf.union(i, j)
        counts.append(len(uf.groups()))
    return counts


def _cluster_band(node_txs, axes, u, m_samples, lam, em_m):
    """Bayesian entity-count posterior band (mean, 2.5%, 97.5%) over node_txs, vs the F-S(EM) point
    partition (edges thresholded at 0.5)."""
    from decluster.fs_em import agree_matrix
    from decluster.fs_bayes import pair_probs
    from decluster.unionfind import UF
    n = len(node_txs)
    node_pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    nA, nmask, _, _ = agree_matrix([(node_txs[i], node_txs[j]) for (i, j) in node_pairs], axes)
    c = sorted(_entity_counts(nA, nmask, u, m_samples, lam, node_pairs, n, seed=0))
    band = (sum(c) / len(c), c[int(0.025 * (len(c) - 1))], c[int(0.975 * (len(c) - 1))])
    pm = pair_probs(nA, nmask, em_m, u, 0.5)
    uf = UF(range(n))
    for (i, j), p in zip(node_pairs, pm):
        if p >= 0.5:
            uf.union(i, j)
    return band, len(uf.groups())


def _reuse_nodes(txs, cap=50):
    """Clear-structure node set: coins from address-reuse groups (bimodal P(match) -> confident partition)."""
    from decluster.change_gt import input_addrs
    by_addr = {}
    for tx in txs:
        for a in sorted(input_addrs(tx)):                   # sorted -> PYTHONHASHSEED-independent
            by_addr.setdefault(a, {})[tx["txid"]] = tx
    groups = [list(g.values()) for g in by_addr.values() if len(g) >= 2]
    node_txs = []
    for g in groups:
        if len(node_txs) >= cap:
            break
        node_txs.extend(g[:3])
    return node_txs[:cap]


def _ambiguous_nodes(txs, axes, m, u, pool_n=300, size=18, seed=1):
    """Ambiguous-structure node set: coins whose pairwise fingerprint agreement is *borderline*
    (intermediate P(match)) — the regime where the owner-partition is genuinely uncertain. Chosen sparse
    (low intermediate-degree) to sit near the percolation threshold, so the entity-count posterior is
    non-degenerate. Deterministic under seed + PYTHONHASHSEED-independent sampling."""
    from decluster.fs_em import agree_matrix
    from decluster.fs_bayes import pair_probs
    from collections import defaultdict
    rng = random.Random(seed)
    pool = rng.sample(txs, min(pool_n, len(txs)))
    n = len(pool)
    pA, pmask, _, _ = agree_matrix([(pool[i], pool[j]) for i in range(n) for j in range(i + 1, n)], axes)
    pm = pair_probs(pA, pmask, m, u, 0.5)
    deg = defaultdict(int)
    k = 0
    for i in range(n):
        for j in range(i + 1, n):
            if 0.2 <= pm[k] <= 0.8:
                deg[i] += 1
                deg[j] += 1
            k += 1
    cand = sorted(deg, key=lambda z: deg[z])                # sparse (low intermediate-degree) first
    step = max(1, len(cand) // size)
    return [pool[i] for i in cand[::step][:size]]


def main(cap=4000):
    from decluster.fingerprint_validate import load_blkcache, reuse_pairs, LibraryScorer
    from decluster.fs_em import agree_matrix, em_fit, oracle_m
    from decluster.fs_bayes import gibbs_fit, pair_probs, ece

    txs = load_blkcache()
    pos, neg = reuse_pairs(txs, cap=cap, seed=0)
    pairs = pos + neg
    labels = [1] * len(pos) + [0] * len(neg)
    axes = LibraryScorer().axes
    A, mask, names, u = agree_matrix(pairs, axes)

    em = em_fit(A, mask, u)
    om = oracle_m(A, mask, labels)
    bayes = gibbs_fit(A, mask, u)

    p_fs95 = pair_probs(A, mask, [0.95] * len(u), u, 0.5)
    p_fsem = pair_probs(A, mask, em["m"], u, 0.5)
    p_bayes = bayes["p_match"]

    print("# Bayesian (Gibbs) vs Fellegi-Sunter on %d txs; %d+%d reuse pairs (per-field likelihood)\n"
          % (len(txs), len(pos), len(neg)))
    print("# AUC (tie control — same evidence):")
    for name, p in (("F-S(0.95)", p_fs95), ("F-S(EM)", p_fsem), ("Bayesian", p_bayes)):
        print("  %-10s AUC %.4f  ECE %.4f" % (name, _auc_split(p, len(pos)), ece(p, labels)))

    print("\n# per-axis m: Bayesian posterior (mean [95%% CI]) vs EM vs oracle vs assumed")
    print("%-22s %-20s %8s %8s %8s" % ("axis", "Bayesian mean[CI]", "EM", "oracle", "assumed"))
    for i, nm in enumerate(names):
        lo, hi = bayes["m_ci"][i]
        oj = ("%.3f" % om[i]) if om[i] is not None else "n/a"
        flag = "  <-- 0.95 outside CI" if not (lo <= 0.95 <= hi) else ""
        print("%-22s %.3f[%.3f,%.3f] %8.3f %8s %8.2f%s"
              % (nm, bayes["m_mean"][i], lo, hi, em["m"][i], oj, 0.95, flag))

    # cluster-level: F-S gives a point; the Bayesian gives a posterior band. Two regimes.
    print("\n# cluster-level entity count (F-S = a point; Bayesian = a posterior band over %d draws):"
          % min(200, len(bayes["m_samples"])))
    rn = _reuse_nodes(txs)
    rb, rb_fs = _cluster_band(rn, axes, u, bayes["m_samples"], bayes["lam_mean"], em["m"])
    print("  clear structure   (%2d reuse-linked nodes): Bayesian mean %.1f band [%d, %d]   F-S(EM) point %d"
          % (len(rn), rb[0], rb[1], rb[2], rb_fs))
    an = _ambiguous_nodes(txs, axes, em["m"], u)
    ab, ab_fs = _cluster_band(an, axes, u, bayes["m_samples"], bayes["lam_mean"], em["m"])
    print("  ambiguous structure (%2d borderline nodes): Bayesian mean %.1f band [%d, %d]   F-S(EM) point %d"
          % (len(an), ab[0], ab[1], ab[2], ab_fs))


if __name__ == "__main__":
    main()
