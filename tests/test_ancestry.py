import math
import pytest
from decluster import ancestry


def _g(transient, absorbers, edges, truncated=0):
    g = ancestry.Graph()
    g.transient, g.absorbers, g.edges, g.truncated = transient, absorbers, edges, truncated
    return g


def test_deterministic_chain_puts_all_mass_on_one_origin():
    # T -> A (single deterministic edge to one absorber)
    g = _g(["T"], ["A"], {"T": [("A", 1.0)]})
    dist = ancestry.absorber_distribution(g, "T")
    assert dist == {"A": 1.0}


def test_split_to_two_absorbers_is_uniform():
    g = _g(["T"], ["A", "B"], {"T": [("A", 0.5), ("B", 0.5)]})
    dist = ancestry.absorber_distribution(g, "T")
    assert dist["A"] == pytest.approx(0.5)
    assert dist["B"] == pytest.approx(0.5)


def test_two_hop_chain_through_transient():
    # T -> M (transient) -> {A:0.5, B:0.5}
    g = _g(["T", "M"], ["A", "B"],
           {"T": [("M", 1.0)], "M": [("A", 0.5), ("B", 0.5)]})
    dist = ancestry.absorber_distribution(g, "T")
    assert dist["A"] == pytest.approx(0.5)
    assert dist["B"] == pytest.approx(0.5)


def test_diamond_shared_ancestor_sums_correctly():
    # T -> {X:0.5, Y:0.5}; X -> A; Y -> A  => all mass on A
    g = _g(["T", "X", "Y"], ["A"],
           {"T": [("X", 0.5), ("Y", 0.5)], "X": [("A", 1.0)], "Y": [("A", 1.0)]})
    dist = ancestry.absorber_distribution(g, "T")
    assert dist["A"] == pytest.approx(1.0)


def test_target_is_absorber_returns_itself():
    g = _g([], ["T"], {})
    assert ancestry.absorber_distribution(g, "T") == {"T": 1.0}
