import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.def1_sparsity import (cosine, feature_vector, nearest_similarities,
                                     survival)
from decluster.views import PseudonymGraph


def test_cosine_basic():
    assert abs(cosine({"a": 1, "b": 1}, {"a": 1, "b": 1}) - 1.0) < 1e-9
    assert cosine({"a": 1}, {"b": 1}) == 0.0
    assert cosine({}, {"a": 1}) == 0.0
    assert abs(cosine({"a": 1, "b": 1}, {"a": 1}) - 1 / (2 ** 0.5)) < 1e-9


def graph(edges, axes=None):
    g = PseudonymGraph()
    for s, d in edges:
        for x in (s, d):
            v = g._vertex(x)
            if axes and x in axes:
                for ax, val in axes[x].items():
                    v["axes"].setdefault(ax, __import__("collections").Counter())[val] += 1
        g.edges[(s, d)] = {"transfers": 1, "value": 1}
        g._out[s].add(d)
        g._in[d].add(s)
    return g


def test_feature_vector_carries_fingerprint_and_structure():
    g = graph([("a", "b")], axes={"a": {"version": "v2"}})
    fv = feature_vector(g, "a")
    assert fv.get("version=v2") == 1.0          # statistical
    assert any(k.startswith("deg=") for k in fv)  # structural
    assert any(k.startswith("nbdeg=") for k in fv)


def test_identical_clusters_read_as_non_sparse():
    """Twenty clusters with the same feature vector: every one has a perfect twin, so the
    survival curve sits at 1.0 — the space is maximally non-sparse, the regime that defeats
    the attack."""
    edges = [(f"h{i}", f"t{i}") for i in range(20)]
    g = graph(edges, axes={f"h{i}": {"version": "v2"} for i in range(20)})
    tops = nearest_similarities(g, query_n=20, background_n=20, min_degree=1)
    s = survival(tops)
    assert s[0.9] == 1.0


def test_distinct_clusters_read_as_sparse():
    """Clusters with disjoint fingerprint axes have no twin: survival near zero at high
    epsilon."""
    edges = [(f"h{i}", f"t{i}") for i in range(20)]
    g = graph(edges, axes={f"h{i}": {"version": f"v{i}"} for i in range(20)})
    # neighbour-degree structure is identical, so similarity is bounded below 1 but the
    # distinctive axis should keep most pairs apart at high epsilon
    tops = nearest_similarities(g, query_n=20, background_n=20, min_degree=1)
    assert survival(tops)[0.99] < 1.0


def test_survival_is_monotone_decreasing_in_epsilon():
    s = survival([0.2, 0.5, 0.85, 0.97])
    vals = [s[e] for e in (0.3, 0.5, 0.7, 0.9, 0.95, 0.99)]
    assert all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1))
