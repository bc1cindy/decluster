import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class _Neutral:
    def score(self, a, b, explain=False):
        return 0.0


def _setup(cl):
    cl.fetch_tx = lambda t: {"txid": t, "vin": [{"txid": "s_" + t, "prevout": {"value": 100}}],
                             "vout": [{"value": 90}]}
    cl._cospent_pairs = lambda nodes: [("A", "B", "T")]


def test_subsetsum_off_matches_no_flag():
    import decluster.cluster as cl
    orig = cl._cospent_pairs
    _setup(cl)
    try:
        a1 = cl.cluster_refined(["A", "B"], _Neutral(), link_above=99)[0]
        a2 = cl.cluster_refined(["A", "B"], _Neutral(), link_above=99, subsetsum=False)[0]
        assert sorted(sorted(g) for g in a1) == sorted(sorted(g) for g in a2)
    finally:
        cl._cospent_pairs = orig


def test_subsetsum_refuses_sparse_conclusive_pair():
    import decluster.cluster as cl
    orig = cl._cospent_pairs
    _setup(cl)
    stub = lambda tx, a, b: -12.0        # a conclusive de-mix refuse for the pair
    try:
        off = cl.cluster_refined(["A", "B"], _Neutral(), link_above=99)[0]
        on = cl.cluster_refined(["A", "B"], _Neutral(), link_above=99, subsetsum=True, _ss_fn=stub)[0]
        assert sorted(sorted(g) for g in off) == [["A", "B"]]      # co-spend prior keeps them together
        assert sorted(sorted(g) for g in on) == [["A"], ["B"]]      # de-mix refuse (-12) splits them
    finally:
        cl._cospent_pairs = orig


def test_default_resolve_routes_to_demix(monkeypatch):
    # With no _ss_fn, the subsetsum path must route each co-spent pair straight to amount_refuse_demix
    # (the de-mix self-gates via its cap; no triage pre-gate).
    import decluster.cluster as cl
    import decluster.subsetsum as ss
    orig = cl._cospent_pairs
    calls = []
    cl.fetch_tx = lambda t: {"txid": t, "vin": [{"txid": "s_" + t, "prevout": {"value": 100}}],
                             "vout": [{"value": 90}]}
    cl._cospent_pairs = lambda nodes: [("A", "B", "T")]
    monkeypatch.setattr(ss, "amount_refuse_demix", lambda tx, a, b, *_: calls.append((a, b)) or 0.0)
    try:
        cl.cluster_refined(["A", "B"], _Neutral(), link_above=99, subsetsum=True)
        assert ("A", "B") in calls
    finally:
        cl._cospent_pairs = orig
