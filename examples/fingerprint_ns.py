"""Regime test: are wallet fingerprints sparse quasi-identifiers or equivalence-class
conditioners? Compares the N-S fingerprint channel (overlap + eccentricity gap) with the
F-S combiner on the same reuse-pairs, over three rarity sources. Offline.
Run from repo root: .venv/bin/python examples/fingerprint_ns.py. See results/RESULTS-fingerprint-regime.md."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decluster import fingerprint_ns as fns
from decluster.fingerprint_validate import load_blkcache
from decluster.fingerprint_regime import build_labeled_nodes, evaluate as run_regime


def main():
    txs = load_blkcache()
    axis_fns = fns.axis_fns()
    lib = fns.library_weights()
    sources = [("library", lib),
               ("measured", fns.measured_weights(txs, axis_fns))]
    lumen_path = os.environ.get("LUMEN_PRIOR")
    have_lumen = bool(lumen_path) and os.path.exists(lumen_path)
    if have_lumen:
        sources.append(("lumen", fns.lumen_weights(lumen_path, lib)))
    print("# Fingerprint regime test on %d txs\n" % len(txs))
    if not have_lumen:
        print("# lumen source skipped: no prior given (set LUMEN_PRIOR to a prior JSON path)\n")
    print("%-10s %8s %8s %9s %9s %13s" % ("source", "NS_AUC", "FS_AUC", "NS_top1", "FS_top1", "within_gap"))
    for label, w in sources:
        r = run_regime(txs, w, label)
        print("%-10s %8.4f %8.4f %9.3f %9.3f %13.3f"
              % (r["weight_source"], r["ns_auc"], r["fs_auc"], r["ns_top1"], r["fs_top1"], r["within_class_gap_mean"]))


if __name__ == "__main__":
    main()
