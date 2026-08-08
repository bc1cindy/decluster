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


from decluster.ancestry import build_extended_graph


def _fetch_factory():
    txs = {
        "t1": {"vin": [{"txid": "t0", "vout": 0, "prevout": {"value": 100}},
                       {"txid": "t0b", "vout": 0, "prevout": {"value": 900}}],
               "vout": [{"value": 1000}]},
        "t0": {"vin": [{"is_coinbase": True}], "vout": [{"value": 100}]},
        "t0b": {"vin": [{"is_coinbase": True}], "vout": [{"value": 900}]},
    }
    return lambda txid: txs[txid]


def test_value_weighting_shifts_edge_mass_to_larger_input():
    oracle = lambda ins, outs: [[1.0] for _ in ins]     # uniform link -> value breaks the tie
    fetch = _fetch_factory()
    g = build_extended_graph(("t1", 0), depth=2, fetch=fetch,
                             link_oracle=oracle, value_weighted=True)
    edges = dict((nxt, w) for nxt, w in g.edges[("t1", 0)])
    assert edges[("t0b", 0)] > edges[("t0", 0)]         # 900-sat parent gets more mass


from decluster.ancestry import build_extended_graph


def _two_parent_fetch():
    txs = {
        "t1": {"vin": [{"txid": "p0", "vout": 0, "prevout": {"value": 500}},
                       {"txid": "p1", "vout": 0, "prevout": {"value": 500}}],
               "vout": [{"value": 1000}]},
        "p0": {"vin": [{"is_coinbase": True}], "vout": [{"value": 500}]},
        "p1": {"vin": [{"is_coinbase": True}], "vout": [{"value": 500}]},
    }
    return lambda txid: txs[txid]


def test_subjective_oracle_none_is_unchanged():
    fetch = _two_parent_fetch()
    oracle = lambda ins, outs: [[1.0] for _ in ins]        # uniform link, one output
    g0 = build_extended_graph(("t1", 0), depth=2, fetch=fetch, link_oracle=oracle)
    g1 = build_extended_graph(("t1", 0), depth=2, fetch=fetch, link_oracle=oracle,
                              subjective_oracle=None)
    assert dict(g0.edges[("t1", 0)]) == dict(g1.edges[("t1", 0)])


def test_subjective_oracle_boosts_a_link_before_solve():
    fetch = _two_parent_fetch()
    oracle = lambda ins, outs: [[1.0] for _ in ins]        # uniform: both inputs equally likely
    # subjective evidence: input 0 -> output 0 is same-owner (boost x9), input 1 unchanged
    sub = lambda tx, ins, outs: [[9.0], [1.0]]
    g = build_extended_graph(("t1", 0), depth=2, fetch=fetch, link_oracle=oracle,
                             subjective_oracle=sub)
    edges = dict(g.edges[("t1", 0)])
    assert edges[("p0", 0)] > edges[("p1", 0)]             # boosted link carries more mass
    assert abs(edges[("p0", 0)] - 0.9) < 1e-9              # 9/(9+1)
    assert abs(edges[("p1", 0)] - 0.1) < 1e-9


def test_subjective_oracle_none_return_abstains():
    fetch = _two_parent_fetch()
    oracle = lambda ins, outs: [[1.0] for _ in ins]
    sub = lambda tx, ins, outs: None                        # abstain -> no reweight
    g = build_extended_graph(("t1", 0), depth=2, fetch=fetch, link_oracle=oracle,
                             subjective_oracle=sub)
    edges = dict(g.edges[("t1", 0)])
    assert abs(edges[("p0", 0)] - 0.5) < 1e-9               # unchanged uniform


def _binary_tree_fetch(max_len):
    """Deterministic full binary ancestry tree: each non-coinbase coin has 2 inputs, keyed by the
    txid's bit-path; a coin becomes coinbase once its path length reaches max_len. The full graph
    at a sufficient depth has 2**(max_len+1) - 1 coins -- strictly more than any small max_nodes cap."""
    def fetch(txid):
        if len(txid) >= max_len:
            return {"vin": [{"is_coinbase": True}], "vout": [{"value": 100}]}
        left, right = txid + "0", txid + "1"
        return {"vin": [{"txid": left, "vout": 0, "prevout": {"value": 100}},
                        {"txid": right, "vout": 0, "prevout": {"value": 100}}],
                "vout": [{"value": 200}]}
    return fetch


_tree_oracle = lambda ins, outs: [[1.0] * len(outs) for _ in ins]


def test_max_nodes_caps_graph_size_and_truncates():
    # full tree at max_len=6 has 127 coins; a cap of 10 must stay near k, not blow up toward 127.
    fetch = _binary_tree_fetch(max_len=6)
    g = build_extended_graph(("", 0), depth=8, fetch=fetch, link_oracle=_tree_oracle, max_nodes=10)
    total = len(g.transient) + len(g.absorbers)
    assert 10 <= total <= 3 * 10       # bounded near k (k committed + one branching layer to drain)
    assert g.truncated > 0


def test_max_nodes_none_reproduces_current_behavior():
    fetch = _two_parent_fetch()
    oracle = lambda ins, outs: [[1.0] for _ in ins]
    g_default = build_extended_graph(("t1", 0), depth=2, fetch=fetch, link_oracle=oracle)
    g_explicit_none = build_extended_graph(("t1", 0), depth=2, fetch=fetch, link_oracle=oracle,
                                           max_nodes=None)
    dist_default = ancestry.absorber_distribution(g_default, ("t1", 0))
    dist_none = ancestry.absorber_distribution(g_explicit_none, ("t1", 0))
    expected = {("p0", 0): 0.5, ("p1", 0): 0.5}
    assert dist_default == pytest.approx(expected)
    assert dist_none == pytest.approx(expected)
    assert dist_default == dist_none


def test_max_nodes_only_truncates_never_invents():
    # max_len=3, cap=6: cap lands mid-tree (levels 0-2 alone total 7 coins), so some non-coinbase
    # interior coins get truncated in the capped run instead of being expanded to their origins.
    fetch = _binary_tree_fetch(max_len=3)
    uncapped = build_extended_graph(("", 0), depth=8, fetch=fetch, link_oracle=_tree_oracle)
    capped = build_extended_graph(("", 0), depth=8, fetch=fetch, link_oracle=_tree_oracle,
                                  max_nodes=6)
    uncapped_coins = set(uncapped.transient) | set(uncapped.absorbers)
    assert set(capped.absorbers) <= uncapped_coins
    assert capped.truncated > 0
