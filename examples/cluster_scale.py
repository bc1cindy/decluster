"""Offline scale measurement of the whole-corpus merge-only baseline (cluster.build_cospend_lookup):
entity reduction over the value-carrying downloads + a window-local vs whole-corpus contrast. No
network. Run from anywhere: python3 examples/cluster_scale.py
Reads ~/Downloads/bquxjob_*.json. See results/RESULTS-cluster-scale.md."""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_all_txs():
    from decluster.measure import load_unique
    paths = sorted(glob.glob(os.path.expanduser("~/Downloads/bquxjob_*.json")))
    return [tx for tx, _ in load_unique(paths)]


def _groups(lookup):
    g = {}
    for node, cid in lookup.items():
        g.setdefault(cid, []).append(node)
    return list(g.values())


def main():
    from decluster.cluster import build_cospend_lookup
    from decluster.graph_metric import partition_entropy, effective_anon_set, largest_cluster_frac
    txs = _load_all_txs()
    print("# corpus: %d unique txs from the downloads\n" % len(txs))

    lk = build_cospend_lookup(txs)
    g = _groups(lk)
    print("# whole-corpus multi-input baseline:")
    print("  funders=%d -> entities=%d (%.1f%% collapse)  entropy=%.2f bits  eff_anon=%.1f  largest=%.4f"
          % (len(lk), len(g), 100 * (1 - len(g) / len(lk)), partition_entropy(g),
             effective_anon_set(g), largest_cluster_frac(g)))

    print("\n# scale curve (corpus fraction -> entities/funder; contiguous chains collapse, scattered ones don't):")
    print("%-8s %10s %10s %10s %12s" % ("frac", "txs", "funders", "entities", "ent/funder"))
    for frac in (0.1, 0.25, 0.5, 0.75, 1.0):
        sub = txs[:max(1, int(len(txs) * frac))]
        ls = build_cospend_lookup(sub); gs = _groups(ls)
        print("%-8.2f %10d %10d %10d %12.4f"
              % (frac, len(sub), len(ls), len(gs), (len(gs) / len(ls)) if ls else 0.0))

    window = txs[:max(1, len(txs) // 10)]
    lk_win = build_cospend_lookup(window)
    win_funders = set(lk_win)

    def entities_over(funders, lookup):
        cids = {}
        for f in funders:
            cids.setdefault(lookup.get(f, ("_solo", f)), []).append(f)
        return len(cids)

    e_local = entities_over(win_funders, lk_win)
    e_whole = entities_over(win_funders, lk)
    print("\n# window-local vs whole-corpus baseline on the SAME %d window funders:" % len(win_funders))
    print("  window-local=%d  whole-corpus=%d  (%d extra merges from co-spends outside the window)"
          % (e_local, e_whole, e_local - e_whole))


if __name__ == "__main__":
    main()
