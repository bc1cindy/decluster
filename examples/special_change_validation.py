"""Validate fingerprint change-id against the value-based optimal-change label (non-circular):
within-tx predictors (no network) + onward-spend fingerprints (live mempool.space fetch, sampled).
Run from repo root: python3 examples/special_change_validation.py [n_onward]
Reads the value-carrying downloads in ~/Downloads/bquxjob_*.json."""
import glob
import os
import random

def _load_value_txs():
    """dedup 2-output txs that carry input values (from the fingerprint-calibration exports)."""
    from decluster.measure import load_ndjson
    seen, txs = set(), []
    for f in sorted(glob.glob(os.path.expanduser("~/Downloads/bquxjob_*.json"))):
        for tx, _h in load_ndjson(f):
            vin0 = (tx.get("vin") or [{}])[0]
            has_val = "value" in vin0.get("prevout", {}) or "value" in vin0
            if not (tx.get("txid") and has_val) or tx["txid"] in seen:
                continue
            seen.add(tx["txid"]); txs.append(tx)
    return txs

def main(n_onward=1500):
    from decluster.change_special import build_gt_special, label_optimal_change, within_tx_rates
    from decluster.change_validate import per_axis_rates
    from decluster.fetch import fetch_tx, fetch_outspends
    txs = _load_value_txs()
    gt = build_gt_special(txs, label_optimal_change)
    print("# optimal-change GT: %d labels (from %d value-carrying txs)" % (len(gt), len(txs)))

    print("\n# within-tx predictors vs optimal-change (no network):")
    print("%-16s %6s %6s %8s" % ("predictor", "TPR", "FPR", "coverage"))
    for name, (t, f, c) in within_tx_rates(gt).items():
        print("%-16s %6.3f %6.3f %8.3f" % (name, t, f, c))

    rng = random.Random(0)
    sample = rng.sample(gt, min(n_onward, len(gt)))
    print("\n# onward-spend fingerprints vs optimal-change (live fetch, n=%d):" % len(sample))
    print("%-16s %6s %6s %8s" % ("axis", "TPR", "FPR", "coverage"))
    for name, (t, f, c) in per_axis_rates(sample, fetch_tx, fetch_outspends).items():
        print("%-16s %6.3f %6.3f %8.3f" % (name, t, f, c))

if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1500)
