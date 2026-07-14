"""test graph-level anonymity metrics"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_partition_entropy():
    from decluster.graph_metric import partition_entropy
    assert abs(partition_entropy([["a"], ["b"], ["c"], ["d"]]) - 2.0) < 1e-9   # 4 singletons -> log2(4)
    assert partition_entropy([["a", "b", "c", "d"]]) == 0.0                     # one cluster -> 0
    assert abs(partition_entropy([["a", "b", "c"], ["d"]]) - 0.8112781) < 1e-6  # 3,1

def test_effective_anon_set():
    from decluster.graph_metric import effective_anon_set
    assert abs(effective_anon_set([["a"], ["b"], ["c"], ["d"]]) - 4.0) < 1e-9
    assert abs(effective_anon_set([["a", "b", "c", "d"]]) - 1.0) < 1e-9

def test_largest_cluster_frac():
    from decluster.graph_metric import largest_cluster_frac
    assert abs(largest_cluster_frac([["a", "b", "c"], ["d"]]) - 0.75) < 1e-9
    assert largest_cluster_frac([]) == 0.0

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print(f"  ok  {name}")
    print("3 passed")
