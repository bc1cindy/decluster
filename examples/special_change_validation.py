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
    from decluster.change_special import (build_gt_special, within_tx_rates, agreement_matrix,
        label_optimal_change, label_round_number, label_type_match, label_address_reuse)
    from decluster.change_validate import per_axis_rates
    from decluster.fetch import fetch_tx, fetch_outspends
    LABELS = {"optimal_change": label_optimal_change, "round_number": label_round_number,
              "type_match": label_type_match, "address_reuse": label_address_reuse}
    txs = _load_value_txs()
    gts = {name: build_gt_special(txs, fn) for name, fn in LABELS.items()}
    print("# special-case labels on %d value-carrying txs:" % len(txs))
    for name, gt in gts.items():
        print("#   %-16s %d labels" % (name, len(gt)))

    print("\n# label agreement matrix (both / agree / disagree):")
    for (a, b), r in agreement_matrix(gts).items():
        print("  %-16s x %-16s both=%-6d agree=%-6d disagree=%-6d"
              % (a, b, r["both"], r["agree"], r["disagree"]))

    print("\n# within-tx predictors vs each label (no network):")
    print("%-16s %-16s %6s %6s %8s" % ("label", "predictor", "TPR", "FPR", "coverage"))
    for name, gt in gts.items():
        for pname, (t, f, c) in within_tx_rates(gt).items():
            print("%-16s %-16s %6.3f %6.3f %8.3f" % (name, pname, t, f, c))

    rng = random.Random(0)
    print("\n# onward-spend per-axis vs each label (live fetch, n<=%d per label):" % n_onward)
    print("%-16s %-14s %6s %6s %8s" % ("label", "axis", "TPR", "FPR", "coverage"))
    for name, gt in gts.items():
        sample = rng.sample(gt, min(n_onward, len(gt)))
        for axis, (t, f, c) in per_axis_rates(sample, fetch_tx, fetch_outspends).items():
            print("%-16s %-14s %6.3f %6.3f %8.3f" % (name, axis, t, f, c))

if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1500)
