"""Weight-sensitivity sweep: how robust is the fingerprint-pair AUC to the assumed disagreement-weight
parameter c (= the same-wallet self-agreement rate m, cravado at 0.95 and not fitted — the epistemically
uncertain knob)? Sweeps c and re-measures on the SAME seeded pairs, so only the weight changes. Offline.
Run from repo root: python3 examples/weight_sensitivity.py [cap]. See results/RESULTS-weight-sensitivity.md."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

C_GRID = (0.60, 0.70, 0.80, 0.90, 0.95, 0.99)


def main(cap=4000):
    from decluster.fingerprint_validate import load_blkcache, evaluate, LibraryScorer
    txs = load_blkcache()
    print("# weight sensitivity on %d witness-bearing txs (.blkcache); same seeded pairs across all c\n"
          % len(txs))
    print("%-5s %10s %10s %8s %9s" % ("c", "pos_mean", "neg_mean", "AUC", "shuffle"))
    for c in C_GRID:
        r = evaluate(txs, LibraryScorer(consistency=c), cap=cap, seed=0)
        print("%-5.2f %+10.2f %+10.2f %8.4f %9.4f"
              % (c, r["pos_mean"], r["neg_mean"], r["auc"], r["shuffle_auc"]))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4000)
