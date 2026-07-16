"""Canonical fingerprint-pair validation: does the library model separate same-wallet tx pairs
(address-reuse label) from random pairs on the witness-bearing .blkcache? Scores pairs with the
canonical library-wide scorer (LibraryScorer, all library axes) and reports AUC. Offline.
Run from repo root: python3 examples/fingerprint_validation.py [cap]"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main(cap=4000):
    from decluster.fingerprint_validate import load_blkcache, evaluate, LibraryScorer
    txs = load_blkcache()
    r = evaluate(txs, LibraryScorer(), cap=cap)
    print("# canonical fingerprint-pair validation on %d witness-bearing txs (.blkcache)" % len(txs))
    print("  same-wallet pair score (mean bits): %s"
          % (round(r["pos_mean"], 2) if r["pos_mean"] is not None else None))
    print("  random pair score (mean bits):      %s"
          % (round(r["neg_mean"], 2) if r["neg_mean"] is not None else None))
    print("  AUC (same-wallet vs random):        %s" % r["auc"])
    print("  shuffle control:                    %s" % r["shuffle_auc"])
    print("  n_pos=%d n_neg=%d" % (r["n_pos"], r["n_neg"]))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4000)
