import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.graph_shape import (assortativity, configuration_transitivity, degrees,
                                   moments, summary, tail_exponent, transitivity)
from decluster.views import PseudonymGraph


def graph(edges):
    g = PseudonymGraph()
    for s, d in edges:
        g._vertex(s), g._vertex(d)
        g.edges[(s, d)] = {"transfers": 1, "value": 1}
        g._out[s].add(d)
        g._in[d].add(s)
    return g


def test_transitivity_of_a_triangle_and_of_a_path():
    assert transitivity(graph([("a", "b"), ("b", "c"), ("c", "a")])) == 1.0
    assert transitivity(graph([("a", "b"), ("b", "c")])) == 0.0


def test_transitivity_is_none_without_a_single_triple():
    assert transitivity(graph([("a", "b")])) is None


def test_assortativity_is_negative_for_a_star():
    """A star is the extreme disassortative shape: every edge joins a hub to a leaf."""
    assert assortativity(graph([("h", f"n{i}") for i in range(10)])) < -0.9


def test_assortativity_is_positive_when_like_degrees_attach():
    """A triangle of degree-2 vertices alongside a lone degree-1 pair: every edge joins
    equals, which is the shape social graphs are said to have."""
    g = graph([("a", "b"), ("b", "c"), ("c", "a"), ("d", "e")])
    assert assortativity(g) > 0.9


def test_assortativity_is_undefined_when_every_degree_is_equal():
    """Zero variance in the degrees leaves no correlation to compute. It must abstain rather
    than report zero, which would read as "measured, and neutral"."""
    assert assortativity(graph([("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")])) is None


def test_configuration_null_rises_with_degree_spread():
    """The null is what the degree sequence alone would produce, so a graph whose clustering
    merely reflects a skewed degree sequence must not read as structured."""
    flat = {f"v{i}": 2 for i in range(100)}
    skew = {**{f"v{i}": 1 for i in range(99)}, "hub": 99}
    assert configuration_transitivity(skew) > configuration_transitivity(flat)


def test_moments_and_tail_exponent_on_a_known_sequence():
    assert moments({"a": 2, "b": 2, "c": 2, "d": 2}) == (2.0, 4.0)
    assert moments({}) == (0.0, 0.0)
    assert tail_exponent({"a": 2, "b": 2}, kmin=2) is None   # all at kmin: no tail to fit
    assert tail_exponent({"a": 4, "b": 4}, kmin=2) > 1


def test_summary_reports_every_field_on_a_small_graph():
    s = summary(graph([("a", "b"), ("b", "c"), ("c", "a"), ("c", "d")]))
    assert s["vertices"] == 4 and s["edges"] == 4
    assert s["transitivity"] is not None and s["configuration_transitivity"] is not None
    assert 0 <= s["degree_1_share"] <= 1


def test_sampling_bounds_the_cost_without_changing_a_uniform_graph():
    ring = graph([(f"v{i}", f"v{(i + 1) % 60}") for i in range(60)])
    full = transitivity(ring)
    part = transitivity(ring, sample=20, rng=random.Random(0))
    assert full == part == 0.0
