"""cluster_refined — the registered engine: order-independent partition refinement that keeps the
N-S cluster-level topology accumulation. Pure/offline: stubs fetch_tx and the combiner, no network."""
import sys, os, itertools
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _stub(cl, pairs):
    cl.fetch_tx = lambda t: {"txid": t, "vin": [{"txid": "seed_" + t, "prevout": {"value": 1000}}],
                             "vout": [{"value": 900}]}
    cl._cospent_pairs = lambda nodes: pairs


class _Neutral:
    def score(self, a, b, explain=False):
        return 0.0


class _Diff:
    def score(self, a, b, explain=False):
        return -5.0


def test_refuses_bare_merge():
    import decluster.cluster as cl
    orig = cl._cospent_pairs
    _stub(cl, [("A", "B", "T")])
    try:
        groups, refused, _ = cl.cluster_refined(["A", "B"], _Diff(), link_above=99)
        assert sorted(sorted(g) for g in groups) == [["A"], ["B"]]     # prior + (-5) net-negative -> refused
        assert any({r[0], r[1]} == {"A", "B"} for r in refused)        # the refusal is recorded
    finally:
        cl._cospent_pairs = orig


def test_preserves_transitivity_and_order_independent():
    import decluster.cluster as cl
    orig = cl._cospent_pairs
    _stub(cl, [("A", "B", "T1"), ("B", "C", "T2")])
    try:
        for order in itertools.permutations(["A", "B", "C"]):
            groups, _r, _l = cl.cluster_refined(list(order), _Neutral(), link_above=99)
            assert sorted(sorted(g) for g in groups) == [["A", "B", "C"]]   # transitive, every order
    finally:
        cl._cospent_pairs = orig


def test_cluster_level_topology_drives_refusal():
    # neutral fingerprint + co-spend prior alone would MERGE; disjoint counterparties (cluster-level
    # topology) flip it to a refusal — proving the N-S cluster-level term is what decides.
    import decluster.cluster as cl
    orig = cl._cospent_pairs
    _stub(cl, [("A", "B", "T")])
    neigh = {"A": {"xa"}, "B": {"xb"}}          # disjoint counterparty neighbourhoods
    try:
        g_merge, _, _ = cl.cluster_refined(["A", "B"], _Neutral(), link_above=99)               # no topo
        g_split, _, _ = cl.cluster_refined(["A", "B"], _Neutral(), neigh=neigh, link_above=99)  # topo on
        assert sorted(sorted(g) for g in g_merge) == [["A", "B"]]     # prior alone -> merge
        assert sorted(sorted(g) for g in g_split) == [["A"], ["B"]]   # cluster-level topo -> refuse
    finally:
        cl._cospent_pairs = orig


def test_coerced_fingerprint_cannot_bypass_topology_refusal():
    # a merge coerces fingerprint uniformity (fp high, >= link_above), but disjoint counterparties
    # (cluster-level topology) refute it. The link scan must NOT re-merge a co-spent pair on the
    # coerced fingerprint alone — the fused fixed-point (amount + topology) decides (§2.1).
    import decluster.cluster as cl
    orig = cl._cospent_pairs
    _stub(cl, [("A", "B", "T")])
    neigh = {"A": {"xa"}, "B": {"xb"}}          # disjoint -> cluster-level topology says different

    class _Coerced:
        def score(self, a, b, explain=False):
            return 5.0                          # attacker copies the fingerprint (>= link_above)
    try:
        groups, _refused, linked = cl.cluster_refined(["A", "B"], _Coerced(), neigh=neigh)
        assert sorted(sorted(g) for g in groups) == [["A"], ["B"]]      # topology refutes the coerced merge
        assert not any({a, b} == {"A", "B"} for a, b, _sc in linked)    # NOT re-linked on fp alone
    finally:
        cl._cospent_pairs = orig


def test_link_adds_edge_common_input_misses():
    # two coins NOT co-spent but sharing a rare fingerprint (score >= link_above) are linked
    import decluster.cluster as cl
    orig = cl._cospent_pairs
    _stub(cl, [])                                # no co-spend edges

    class _Strong:
        def score(self, a, b, explain=False):
            return 6.0
    try:
        groups, _r, linked = cl.cluster_refined(["A", "B"], _Strong(), link_above=4.0)
        assert sorted(sorted(g) for g in groups) == [["A", "B"]]
        assert any({a, b} == {"A", "B"} for a, b, _sc in linked)      # recorded as an added link
    finally:
        cl._cospent_pairs = orig


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
