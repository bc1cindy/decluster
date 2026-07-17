"""EM per-axis m: fit the Fellegi-Sunter m per axis by unsupervised EM over the reuse_pairs mixture
(labels withheld), and compare to the assumed 0.95 and the held-out reuse-label oracle. Reports: the
per-axis table, whether EM alone recovers the label (AUC of the posterior), and the pair-AUC with per-
axis fitted m vs 0.95 vs oracle. Offline. Run from repo root: python3 examples/em_m_fit.py [cap].
See results/RESULTS-em-m.md."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main(cap=4000):
    from decluster.fingerprint_validate import load_blkcache, reuse_pairs, evaluate, LibraryScorer
    from decluster.fs_em import agree_matrix, em_fit, oracle_m
    from decluster.graph_deanon import auc

    txs = load_blkcache()
    pos, neg = reuse_pairs(txs, cap=cap, seed=0)
    pairs = pos + neg
    labels = [1] * len(pos) + [0] * len(neg)
    axes = LibraryScorer().axes
    A, mask, names, u = agree_matrix(pairs, axes)

    fit = em_fit(A, mask, u)                     # unsupervised: labels NOT passed
    om = oracle_m(A, mask, labels)               # supervised oracle
    m_em = fit["m"]

    print("# EM per-axis m on %d witness-bearing txs; %d+%d pairs (labels withheld from EM)\n"
          % (len(txs), len(pos), len(neg)))
    print("# lambda (match fraction EM inferred, ~0.5 by enrichment): %.3f  iters=%d"
          % (fit["lam"], fit["n_iter"]))
    print("\n%-22s %8s %8s %8s %8s" % ("axis", "u", "m_EM", "oracle", "assumed"))
    for name, uj, me, oj in zip(names, u, m_em, om):
        print("%-22s %8.3f %8.3f %8s %8.2f"
              % (name, uj, me, ("%.3f" % oj) if oj is not None else "n/a", 0.95))

    r_pos = fit["r"][:len(pos)]
    r_neg = fit["r"][len(pos):]
    print("\n# does EM alone recover the reuse label? AUC of the posterior r: %.4f"
          % auc(r_pos, r_neg, 0))

    m_dict = {name: me for name, me in zip(names, m_em)}
    o_dict = {name: (oj if oj is not None else 0.95) for name, oj in zip(names, om)}
    a_base = evaluate(txs, LibraryScorer(consistency=0.95), cap=cap, seed=0)["auc"]
    a_em = evaluate(txs, LibraryScorer(consistency=m_dict), cap=cap, seed=0)["auc"]
    a_or = evaluate(txs, LibraryScorer(consistency=o_dict), cap=cap, seed=0)["auc"]
    print("\n# pair-AUC by per-axis m source:")
    print("  assumed 0.95 : %.4f" % a_base)
    print("  EM-fitted    : %.4f" % a_em)
    print("  oracle       : %.4f" % a_or)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4000)
