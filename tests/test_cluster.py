"""cluster_from_index / build_cospend_lookup — pure, offline (no fetch_tx)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_cluster_from_index_groups():
    from decluster.cluster import cluster_from_index
    g = cluster_from_index(["A", "B", "C"], {"A": 1, "B": 1, "C": 2})
    assert sorted(sorted(x) for x in g) == [["A", "B"], ["C"]]

def test_cluster_from_index_unknown_is_singleton():
    from decluster.cluster import cluster_from_index
    g = cluster_from_index(["A", "D", "E"], {"A": 1})   # D, E absent -> each its own group
    assert sorted(sorted(x) for x in g) == [["A"], ["D"], ["E"]]

def test_build_cospend_lookup_transitive():
    from decluster.cluster import build_cospend_lookup
    # F1,F2 co-spent in T1 ; F2,F3 co-spent in T2 -> F1,F2,F3 one cluster (transitive, whole-corpus)
    corpus = [
        {"txid": "T1", "vin": [{"txid": "F1"}, {"txid": "F2"}], "vout": []},
        {"txid": "T2", "vin": [{"txid": "F2"}, {"txid": "F3"}], "vout": []},
    ]
    lk = build_cospend_lookup(corpus)
    assert lk["F1"] == lk["F2"] == lk["F3"]

def test_build_cospend_lookup_separates_uncospent():
    from decluster.cluster import build_cospend_lookup
    corpus = [
        {"txid": "T1", "vin": [{"txid": "F1"}, {"txid": "F2"}], "vout": []},
        {"txid": "T2", "vin": [{"txid": "F4"}], "vout": []},          # F4 never co-spent
    ]
    lk = build_cospend_lookup(corpus)
    assert lk["F1"] == lk["F2"]
    assert lk["F4"] != lk["F1"]

def test_overcount_report_uses_baseline_lookup():
    import decluster.graph_metric as gm
    import decluster.cluster as cl
    orig = cl.cluster_refined
    cl.cluster_refined = lambda nodes, combiner: ([[n] for n in nodes], [], [])   # stub the engine: no network
    try:
        # A and B share a cluster_id -> the baseline (union_find) is ONE cluster of two coins
        rep = gm.overcount_report(["A", "B"], combiner=None, baseline_lookup={"A": 1, "B": 1})
        assert rep["union_find"]["clusters"] == 1
        assert rep["fingerprint_aware"]["clusters"] == 2   # stub kept them separate
    finally:
        cl.cluster_refined = orig

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
