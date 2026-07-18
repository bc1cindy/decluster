"""graph-topology weight (counterparty overlap) as a calibrated Fellegi-Sunter quasi-identifier.

Honest scope (see results/RESULTS-topology.md):
- MATCH side (shared counterparties) is rarity-weighted; a shared *rare* counterparty is strong
  same-owner evidence, a common hub ~0 bits.
- The false-positive control for a same-software payjoin is the CLUSTER-LEVEL rarity-weighted
  overlap with a distinctiveness threshold `topo_tau`: an overlap below tau (disjoint, or sharing
  only non-distinctive hubs) is treated as disjoint (~-8 bits) and the merge is refused. The
  threshold separates same-owner from different-owner overlap at AUC 1.00 on a real slice
  (`calibrate_topo_tau`). Distinctiveness is judged by GLOBAL rarity, so it is field-independent.
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
    # a fingerprint match of ~+2.78 (same wallet) outweighs it: +2.78 + (-1.65) = +1.13 -> NOT refused.
    # per-pair topology cannot refuse the same-software payjoin; that needs cluster-level topology.

def test_cluster_topology_weight_tau_threshold():
    from decluster.cluster import counterparty_bits, cluster_topology_weight
    # HUB touched by everyone -> ~0 bits (non-distinctive); Carol touched by 2 -> rare.
    neigh = {"A": {"Carol", "HUB"}, "B": {"Carol", "HUB"}, "C": {"HUB"}}
    neigh.update({f"X{i}": {"HUB"} for i in range(18)})
    cbits = counterparty_bits(neigh)
    assert cbits["HUB"] < 0.5 and cbits["Carol"] > 2.0
    # A,C overlap only the common HUB -> below tau -> treated as disjoint (refuse). Global rarity,
    # so a universal hub (0 bits) is correctly refused regardless of any candidate field.
    assert cluster_topology_weight(["A"], ["C"], neigh, cbits, tau=1.0) < 0
    # A,B share the rare Carol -> above tau -> positive same-owner evidence
    assert cluster_topology_weight(["A"], ["B"], neigh, cbits, tau=1.0) > 1.0
    # legacy tau=0 keeps any shared counterparty (even the hub)
    assert cluster_topology_weight(["A"], ["C"], neigh, cbits, tau=0.0) >= 0.0

def _tx(txid, ins, nseq=0xfffffffd, lt=0, nout=1):
    return {"txid": txid, "locktime": lt,
            "vin": [{"txid": fu, "vout": 0, "sequence": nseq, "prevout": {"value": 100000}} for fu in ins],
            "vout": [{"value": 50000} for _ in range(nout)]}

def test_cluster_topology_refuses_same_software_payjoin():
    """End-to-end: Alice (A1,A2) and Bob (B1,B2) use the SAME wallet; each consolidates their own
    coins, then payjoin P co-spends A1 and B1. Their counterparty circles are disjoint (Carol* vs
    Dave*). The cluster-level rarity-weighted overlap (built confident-first) refuses the payjoin."""
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

    g0, _r0, _ = C.cluster_refined(nodes, cmb)                    # no topology -> collapse
    assert any("A1" in g and "B1" in g for g in g0), "baseline should collapse the payjoin"

    g1, refused, _ = C.cluster_refined(nodes, cmb, neigh=neigh)   # cluster-level topology
    for g in g1:
        assert not ("A1" in g and "B1" in g), "cluster topology must keep Alice and Bob apart"
    assert any("A1" in g and "A2" in g for g in g1), "Alice's own coins stay clustered"
    assert any(set(x[:2]) == {"A1", "B1"} for x in refused), "the A1/B1 merge must be refused"

def test_engine_refuses_hub_only_partial_overlap():
    """Partial overlap (not disjoint): Alice and Bob share only a common HUB (touched by many ->
    ~0 rarity bits). Alice's own coins share her distinctive rare 'Carol', Bob's share 'Dave'. The
    rarity threshold keeps Alice's/Bob's own merges but treats the hub-only Alice/Bob overlap as
    below-tau -> disjoint -> the same-wallet payjoin is refused. Global rarity, so this does NOT
    depend on which clusters happen to be in any candidate window."""
    from decluster import cluster as C
    from decluster.combiner import Combiner
    TXS = {
        "A1": _tx("A1", ["gA"]), "A2": _tx("A2", ["gA"]),
        "B1": _tx("B1", ["gB"]), "B2": _tx("B2", ["gB"]),
        "CA": _tx("CA", ["A1", "A2"], nout=1), "CB": _tx("CB", ["B1", "B2"], nout=1),
        "P":  _tx("P", ["A1", "B1"], nout=3),
    }
    decoys = [f"Z{i}" for i in range(8)]
    for z in decoys: TXS[z] = _tx(z, ["ext"])          # funder not in nodes -> singleton cluster
    C.fetch_tx = lambda txid: TXS[txid]
    nodes = {"A1", "A2", "B1", "B2", "CA", "CB", "P", *decoys}
    cmb = Combiner.from_library()
    neigh = {"A1": {"Carol", "HUB"}, "A2": {"Carol", "HUB"},
             "B1": {"Dave", "HUB"}, "B2": {"Dave", "HUB"}}
    for z in decoys: neigh[z] = {"HUB"}                 # HUB common -> ~0 bits -> non-distinctive
    g, refused, _ = C.cluster_refined(nodes, cmb, neigh=neigh)
    assert any(set(x[:2]) == {"A1", "B1"} for x in refused), "hub-only overlap must not rescue the payjoin"
    for grp in g:
        assert not ("A1" in grp and "B1" in grp), "Alice and Bob must stay apart"
    assert any("A1" in grp and "A2" in grp for grp in g), "Alice's own distinctive coins stay clustered"
    assert any("B1" in grp and "B2" in grp for grp in g), "Bob's own distinctive coins stay clustered"

def test_calibrate_topo_tau_smoke():
    from decluster.cluster import calibrate_topo_tau
    # synthetic 'sample' shape accepted by graph_deanon.build: list of (tx, height). Two owners:
    # {A,B}<->Carol and {C,D}<->Dave. Same-owner halves share their counterparty; cross share none.
    def tx(txid, ins, outs):
        return ({"txid": txid,
                 "vin": [{"prevout": {"scriptpubkey_address": a}} for a in ins],
                 "vout": [{"scriptpubkey_address": a} for a in outs]}, 0)
    sample = [tx("t1", ["A", "B"], ["Carol"]), tx("t2", ["A", "B"], ["Carol"]),
              tx("t3", ["C", "D"], ["Dave"]),  tx("t4", ["C", "D"], ["Dave"])]
    n, same, cross, a = calibrate_topo_tau(sample)
    assert n == 2
    assert same > cross            # same-owner overlap bits exceed cross-owner
    assert a >= 0.5                # separable

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
