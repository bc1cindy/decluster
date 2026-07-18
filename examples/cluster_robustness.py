"""Clustering weight-robustness: does fusing the graph-topology term make the owner-partition stable
under a fingerprint-weight (c) sweep, where a fingerprint-only clustering moves? Builds a controlled
ancestry-shaped scenario (per-wallet fingerprints + distinctive counterparties, cross-wallet payjoins),
runs cluster_refined (the registered engine) in two arms (neigh=None vs neigh=NEIGH) across c, and reports ARI vs each arm's
c=0.95 baseline. Offline, deterministic. Run from repo root: python3 examples/cluster_robustness.py.
See results/RESULTS-cluster-robustness.md."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

C_GRID = (0.60, 0.70, 0.80, 0.90, 0.95, 0.99)
WALLETS = {"A": (0xFFFFFFFD, 0), "B": (0xFFFFFFFF, 0), "C": (0xFFFFFFFE, 500000), "D": (0x00000001, 500000)}


def _tx(txid, ins, nseq, lt, nout):
    return {"txid": txid, "locktime": lt,
            "vin": [{"txid": fu, "vout": 0, "sequence": nseq, "prevout": {"value": 100000}} for fu in ins],
            "vout": [{"value": 50000} for _ in range(nout)]}


def build_scenario():
    """4 wallets, each 3 coins + a consolidation; 2 cross-wallet payjoins. Returns (nodes, neigh, txmap)."""
    txmap, neigh, nodes = {}, {}, set()
    for w, (nseq, lt) in WALLETS.items():
        coins = [f"{w}{i}" for i in (1, 2, 3)]
        for c in coins:
            txmap[c] = _tx(c, [f"g{w}"], nseq, lt, 1)     # each coin is a tx spending the wallet source
            neigh[c] = {f"{w}_rare", "HUB"}
            nodes.add(c)
        txmap[f"C{w}"] = _tx(f"C{w}", coins, nseq, lt, 1)  # consolidation co-spends the 3 coins
        nodes.add(f"C{w}")
    for pj, (x, y) in (("PAB", ("A1", "B1")), ("PCD", ("C1", "D1"))):
        txmap[pj] = _tx(pj, [x, y], 0xFFFFFFFD, 0, 2)     # payjoin: 2-in/2-out equal -> amount neutral
        nodes.add(pj)
    return nodes, neigh, txmap


def _partition(nodes, c, neigh):
    from decluster.combiner import Combiner
    from decluster.cluster import cluster_refined
    groups, _refused, _linked = cluster_refined(nodes, Combiner.from_library(consistency=c), neigh=neigh)
    return groups


def run():
    from decluster import cluster as C
    from decluster.graph_metric import adjusted_rand_index, effective_anon_set
    nodes, neigh, txmap = build_scenario()
    C.fetch_tx = txmap.__getitem__                          # runner-local offline shim

    base_fp = _partition(nodes, 0.95, None)
    base_tp = _partition(nodes, 0.95, neigh)
    print("# clustering weight-robustness on a controlled scenario: %d nodes, 4 wallets, 2 payjoins\n"
          % len(nodes))
    print("%-5s %12s %12s %12s %12s" % ("c", "ARI_fp", "ARI_fp+topo", "eff_fp", "eff_fp+topo"))
    for c in C_GRID:
        pf = _partition(nodes, c, None)
        pt = _partition(nodes, c, neigh)
        print("%-5.2f %12.4f %12.4f %12.2f %12.2f"
              % (c, adjusted_rand_index(pf, base_fp), adjusted_rand_index(pt, base_tp),
                 effective_anon_set(pf), effective_anon_set(pt)))


if __name__ == "__main__":
    run()
