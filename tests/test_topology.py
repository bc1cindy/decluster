"""graph-topology weight (counterparty overlap) as a calibrated Fellegi-Sunter quasi-identifier.

Honest scope (see results/RESULTS-topology.md):
- MATCH side (shared counterparties) is calibrated to real rarity bits and validated
  (AUC 0.84 on a real slice): a shared *rare* counterparty is strong same-owner evidence.
- MISMATCH side (disjoint) is calibrated *weak* (~-1.65 bits); a single disjoint pair
  cannot by itself refuse a same-wallet payjoin. The false-positive control the collaborator
  describes ("enough distinguishing relationships") is a cluster-level N-S accumulation,
  still future work — NOT this per-pair term.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_topology_corroborates_via_shared_rare_counterparty():
    from decluster.cluster import counterparty_bits, topology_weight
    # A0,A1 (same owner) share a RARE counterparty "Carol"; a hub H is touched by everyone.
    neigh = {"A0": {"Carol", "H"}, "A1": {"Carol", "H"}}
    neigh.update({f"X{i}": {"H"} for i in range(23)})     # 23 others touch only the hub
    cbits = counterparty_bits(neigh)
    assert cbits["Carol"] > cbits["H"], "a rare counterparty must outweigh a hub"
    w = topology_weight("A0", "A1", neigh, cbits)
    assert w > 3.0, f"shared rare counterparty -> strong same-owner bits (got {w:+.2f})"

def test_topology_disjoint_is_weak_calibrated_honest_limit():
    from decluster.cluster import topology_weight
    neigh = {"A1": {"C1", "C2", "C3"}, "B1": {"D1", "D2", "D3"}}   # disjoint circles
    w = topology_weight("A1", "B1", neigh, cbits={})               # no shared -> disjoint branch
    assert -3.0 < w < 0.0, f"disjoint should be a WEAK negative, not an inflated penalty (got {w:+.2f})"
    # a fingerprint match of ~+2.78 (same wallet) dominates: +2.78 + (-1.65) = +1.13 -> NOT refused.
    # per-pair topology cannot refuse the same-software payjoin; that needs cluster-level N-S.

def _tx(txid, ins, nseq=0xfffffffd, lt=0, nout=1):
    return {"txid": txid, "locktime": lt,
            "vin": [{"txid": fu, "vout": 0, "sequence": nseq, "prevout": {"value": 100000}} for fu in ins],
            "vout": [{"value": 50000} for _ in range(nout)]}

def test_cluster_topology_refuses_same_software_payjoin():
    """End-to-end proof of the collaborator's mechanism: Alice (A1,A2) and Bob (B1,B2) use the
    SAME wallet; each consolidates their own coins, then payjoin P co-spends A1 and B1. Their
    counterparty circles are disjoint (Carol* vs Dave*). Per-pair topology is too weak, but the
    CLUSTER-LEVEL aggregate (built confident-first) refuses the payjoin (~-8 calibrated bits)."""
    from decluster import cluster as C
    from decluster.combiner import Combiner
    TXS = {
        "A1": _tx("A1", ["gA"]), "A2": _tx("A2", ["gA"]),
        "B1": _tx("B1", ["gB"]), "B2": _tx("B2", ["gB"]),
        "CA": _tx("CA", ["A1", "A2"], nout=1),   # Alice consolidates (2-in/1-out -> amount 0)
        "CB": _tx("CB", ["B1", "B2"], nout=1),   # Bob consolidates
        "P":  _tx("P", ["A1", "B1"], nout=3),    # payjoin (2-in/3-out -> amount 0)
    }
    C.fetch_tx = lambda txid: TXS[txid]
    nodes = {"A1", "A2", "B1", "B2", "CA", "CB", "P"}
    cmb = Combiner.from_library()
    neigh = {"A1": {"Ca", "Cb", "Cc"}, "A2": {"Ca", "Cb", "Cc"},
             "B1": {"Da", "Db", "Dc"}, "B2": {"Da", "Db", "Dc"}}

    g0, _r0, _ = C.cluster_fused(nodes, cmb)                    # no topology -> collapse
    assert any("A1" in g and "B1" in g for g in g0), "baseline should collapse the payjoin"

    g1, refused, _ = C.cluster_fused(nodes, cmb, neigh=neigh)   # cluster-level topology
    for g in g1:
        assert not ("A1" in g and "B1" in g), "cluster topology must keep Alice and Bob apart"
    assert any("A1" in g and "A2" in g for g in g1), "Alice's own coins stay clustered"
    assert any(set(x[:2]) == {"A1", "B1"} for x in refused), "the A1/B1 merge must be refused"

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
