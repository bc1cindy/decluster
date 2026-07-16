"""Phase 2: both change labels on the SAME value-carrying contiguous slice — co-spend
(build_gt_slice_mn) vs optimal-change (label_optimal_change) — to isolate the label effect from
epoch, and to score cluster findNext NON-circularly against the value label (nulling the fingerprint
should DROP the score toward its changeC-only floor, unlike against the co-spend label where it
stayed ~0.66). Offline (reads a local slice, no network).
Run from repo root: python3 examples/two_label_validation.py slice_values.json"""
import sys

def main(paths):
    import decluster.change_cluster as cc
    from decluster.change_slice import load_slice, build_gt_slice_mn, slice_fetchers
    from decluster.change_special import build_gt_special, label_optimal_change, label_agreement
    from decluster.change_validate import per_axis_rates
    from decluster.change_cluster import build_cluster_fingerprints, cluster_rates

    by_txid, spender, uf = load_slice(paths)
    get_tx, get_os = slice_fetchers(by_txid, spender)
    gt_cs, dropped = build_gt_slice_mn(by_txid, uf)
    gt_val = build_gt_special(list(by_txid.values()), label_optimal_change)
    print("# slice: %d txs | co-spend labels: %d | optimal-change labels: %d"
          % (len(by_txid), len(gt_cs), len(gt_val)))
    print("# label agreement (shared txs): %r" % (label_agreement(gt_cs, gt_val),))

    print("\n# per-axis TPR vs BOTH labels on the SAME txs (isolates label from epoch):")
    print("%-14s %14s %14s" % ("axis", "co-spend TPR", "value TPR"))
    ra = per_axis_rates(gt_cs, get_tx, get_os)
    rb = per_axis_rates(gt_val, get_tx, get_os)
    for k in ra:
        print("%-14s %14.3f %14.3f" % (k, ra[k][0], rb[k][0]))

    tfc, afc, cidx = build_cluster_fingerprints(by_txid, uf)
    real = cluster_rates(gt_val, uf, tfc, afc, cidx, get_tx, get_os, use_afc=False)
    cc.tx_features = lambda tx: ("CONST",)                 # null the construction fingerprint
    tfc0, afc0, cidx0 = build_cluster_fingerprints(by_txid, uf)
    nulled = cluster_rates(gt_val, uf, tfc0, afc0, cidx0, get_tx, get_os, use_afc=False)
    print("\n# findNext vs the VALUE label (non-circular; the drop when the fingerprint is nulled is")
    print("# the signal — the NULLED row keeps a changeC/cluster-index floor, it does NOT go to zero,")
    print("# so read the DROP, not the absolute nulled number):")
    print("  findNext TFC+changeC:        TPR=%.3f FPR=%.3f cov=%.3f" % real)
    print("  findNext fingerprint NULLED: TPR=%.3f FPR=%.3f cov=%.3f  (changeC-only floor)" % nulled)

if __name__ == "__main__":
    main(sys.argv[1:])
