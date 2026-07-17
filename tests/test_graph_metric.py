"""adjusted_rand_index: partition-agreement metric for clustering robustness."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def test_ari_identical_is_one():
    from decluster.graph_metric import adjusted_rand_index
    p = [["a", "b"], ["c", "d"]]
    assert adjusted_rand_index(p, p) == 1.0
    assert adjusted_rand_index([["a", "b", "c"]], [["a", "b", "c"]]) == 1.0


def test_ari_hand_verified_value():
    from decluster.graph_metric import adjusted_rand_index
    # {ab}{cd} vs {abc}{d}: index=1, expected=1, max=2.5 -> ARI = 0.0 (hand-computed)
    a = [["a", "b"], ["c", "d"]]
    b = [["a", "b", "c"], ["d"]]
    assert abs(adjusted_rand_index(a, b) - 0.0) < 1e-9


def test_ari_singletons_vs_one_cluster():
    from decluster.graph_metric import adjusted_rand_index
    a = [["a"], ["b"], ["c"]]
    b = [["a", "b", "c"]]
    assert abs(adjusted_rand_index(a, b) - 0.0) < 1e-9


def test_ari_symmetric():
    from decluster.graph_metric import adjusted_rand_index
    a = [["a", "b"], ["c", "d"]]
    b = [["a", "b", "c"], ["d"]]
    assert adjusted_rand_index(a, b) == adjusted_rand_index(b, a)


def test_topology_stabilises_partition_under_c_perturbation():
    from decluster import cluster as C
    from decluster.combiner import Combiner
    from decluster.graph_metric import adjusted_rand_index
    from examples.cluster_robustness import build_scenario, _partition
    nodes, neigh, txmap = build_scenario()
    C.fetch_tx = txmap.__getitem__
    base_fp, base_tp = _partition(nodes, 0.95, None), _partition(nodes, 0.95, neigh)
    lo_fp, lo_tp = _partition(nodes, 0.60, None), _partition(nodes, 0.60, neigh)
    ari_fp = adjusted_rand_index(lo_fp, base_fp)
    ari_tp = adjusted_rand_index(lo_tp, base_tp)
    assert ari_tp >= ari_fp, f"topology should not be less stable than fp-only (topo {ari_tp} < fp {ari_fp})"
    assert ari_tp == 1.0, f"topology-fused partition should be stable across c (got {ari_tp})"
