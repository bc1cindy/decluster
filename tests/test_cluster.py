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

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
