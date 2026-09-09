"""The cut the framework states its positive properties over, measured rather than asserted.

Robust connectivity and own-origin robustness are both the size of a minimum cut: how many coins a
separation would have to take before an output stops reaching its candidate origins. `path_count`
answers a different question — it weights routes by link probability, and many routes may run
through the same coin — so a large count there is consistent with a cut of one.

Three modelling decisions carry the answer, and each is pinned below because getting any of them
wrong returns a plausible number rather than an error: a coin is an edge and not a vertex, the
target is the query point rather than a resource routes compete for, and flow decomposition has to
spend a saturated arc once per unit it carries.
"""

import pytest

from decluster.ancestry import Graph
from decluster.disjoint_routes import cut_size, route_capacity


def graph(edges, absorbers):
    built = Graph()
    built.edges = {coin: [(nxt, 1.0 / len(nexts)) for nxt in nexts]
                   for coin, nexts in edges.items()}
    built.absorbers = list(absorbers)
    return built


TARGET = ("T", 0)


def test_two_independent_routes_are_two():
    g = graph({TARGET: [("a", 0), ("b", 0)], ("a", 0): [("A", 0)], ("b", 0): [("B", 0)]},
              [("A", 0), ("B", 0)])
    assert cut_size(g, TARGET) == 2


def test_a_shared_coin_is_a_cut_of_one():
    """Two origins, but every route runs through one coin: taking it separates the target."""
    g = graph({TARGET: [("x", 0)], ("x", 0): [("A", 0), ("B", 0)]}, [("A", 0), ("B", 0)])
    assert cut_size(g, TARGET) == 1


def test_routes_ending_at_one_origin_do_not_both_count():
    """Three ways out, two of them landing on the same origin coin, is a capacity of two."""
    g = graph({TARGET: [("a", 0), ("b", 0), ("c", 0)],
               ("a", 0): [("A", 0)], ("b", 0): [("A", 0)], ("c", 0): [("B", 0)]},
              [("A", 0), ("B", 0)])
    assert cut_size(g, TARGET) == 2


def test_an_origin_the_target_cannot_reach_is_not_an_origin():
    g = graph({TARGET: []}, [("A", 0)])
    assert cut_size(g, TARGET) == 0


def test_the_target_is_not_a_resource_its_own_routes_compete_for():
    """Every route leaves the target; charging its coin would cap every graph at one."""
    g = graph({TARGET: [("a", 0), ("b", 0), ("c", 0)],
               ("a", 0): [("A", 0)], ("b", 0): [("B", 0)], ("c", 0): [("C", 0)]},
              [("A", 0), ("B", 0), ("C", 0)])
    assert cut_size(g, TARGET) == 3


def test_the_reported_routes_share_no_coin_beyond_the_target():
    g = graph({TARGET: [("a", 0), ("b", 0)], ("a", 0): [("A", 0)], ("b", 0): [("B", 0)]},
              [("A", 0), ("B", 0)])
    count, routes = route_capacity(g, TARGET)
    assert len(routes) == count
    beyond = [coin for route in routes for coin in route[1:]]
    assert len(beyond) == len(set(beyond)), "a reported route reuses a coin another one took"


def test_a_route_is_reported_for_every_unit_of_capacity():
    """Decomposition spends a saturated arc once per unit; marking it used truncates the walk."""
    g = graph({TARGET: [("a", 0), ("b", 0), ("c", 0)],
               ("a", 0): [("A", 0)], ("b", 0): [("B", 0)], ("c", 0): [("C", 0)]},
              [("A", 0), ("B", 0), ("C", 0)])
    count, routes = route_capacity(g, TARGET)
    assert count == 3 and len(routes) == 3


def test_a_deeper_graph_counts_the_narrowest_layer():
    """A cut is as small as the tightest layer, however wide the graph is elsewhere."""
    g = graph({TARGET: [("a", 0), ("b", 0)],
               ("a", 0): [("m", 0)], ("b", 0): [("m", 0)],           # both funnel through m
               ("m", 0): [("A", 0), ("B", 0), ("C", 0)]},
              [("A", 0), ("B", 0), ("C", 0)])
    assert cut_size(g, TARGET) == 1


def test_explicit_origins_override_the_absorber_boundary():
    g = graph({TARGET: [("a", 0), ("b", 0)], ("a", 0): [("A", 0)], ("b", 0): [("B", 0)]},
              [("A", 0), ("B", 0)])
    assert cut_size(g, TARGET, origins=[("A", 0)]) == 1


def test_routes_may_share_a_transaction_but_not_a_coin():
    """The distinction the specification settles, and the reason it is edges and not vertices.

    Two routes leaving the target descend from the same transaction through different outputs. Coins
    are what a seizure or a label removes, so that is two routes; requiring the transactions to
    differ as well would report one, and on a real graph almost everything shares a transaction with
    almost everything.
    """
    g = graph({TARGET: [("p", 0), ("q", 0)],
               ("p", 0): [("M", 0)],          # one output of M
               ("q", 0): [("M", 1)],          # a different output of the same transaction
               ("M", 0): [("A", 0)], ("M", 1): [("B", 0)]},
              [("A", 0), ("B", 0)])
    count, routes = route_capacity(g, TARGET)
    assert count == 2
    assert {coin for route in routes for coin in route} >= {("M", 0), ("M", 1)}


def test_two_routes_through_one_output_of_that_transaction_are_one():
    """The contrast: same transaction and same output is a shared coin, so the cut is one."""
    g = graph({TARGET: [("p", 0), ("q", 0)],
               ("p", 0): [("M", 0)], ("q", 0): [("M", 0)],
               ("M", 0): [("A", 0), ("B", 0)]},
              [("A", 0), ("B", 0)])
    assert cut_size(g, TARGET) == 1


def valued(edges, absorbers, values):
    g = graph(edges, absorbers)
    g.values = values
    return g


def test_a_route_too_small_to_carry_the_coin_is_not_a_route():
    """The specification prunes this way: a path worth less than the amount may have been removed.

    Counting it makes redundancy look larger than it is, which is the wrong direction for a measure
    of fragility — the same overstatement this module exists to correct in the origin count.
    """
    g = valued({TARGET: [("big", 0), ("dust", 0)],
                ("big", 0): [("A", 0)], ("dust", 0): [("B", 0)]},
               [("A", 0), ("B", 0)],
               {TARGET: 1_000_000, ("big", 0): 5_000_000, ("dust", 0): 1_000,
                ("A", 0): 9_000_000, ("B", 0): 1_000})
    from decluster.disjoint_routes import TARGET_VALUE
    assert cut_size(g, TARGET) == 2
    assert cut_size(g, TARGET, carries=TARGET_VALUE) == 1


def test_a_threshold_below_every_coin_prunes_nothing():
    g = valued({TARGET: [("a", 0), ("b", 0)], ("a", 0): [("A", 0)], ("b", 0): [("B", 0)]},
               [("A", 0), ("B", 0)],
               {TARGET: 500, ("a", 0): 900, ("b", 0): 900, ("A", 0): 900, ("B", 0): 900})
    assert cut_size(g, TARGET, carries=100) == 2


def test_pruning_recomputes_reachability_rather_than_only_dropping_coins():
    """A coin that survives the threshold but whose only way onward did not is no longer a route."""
    g = valued({TARGET: [("a", 0)], ("a", 0): [("thin", 0)], ("thin", 0): [("A", 0)]},
               [("A", 0)],
               {TARGET: 1_000, ("a", 0): 9_000, ("thin", 0): 10, ("A", 0): 9_000})
    assert cut_size(g, TARGET, carries=1_000) == 0


def test_flow_capacity_is_the_value_the_origins_could_deliver():
    """The mass the framework states its property over, which counting routes cannot see.

    Two routes both pass a per-route threshold and are both disjoint, so counting says two and
    pruning says two. Together they carry less than the coin is worth, which only capacity says.
    """
    from decluster.disjoint_routes import flow_capacity
    g = valued({TARGET: [("a", 0), ("b", 0)], ("a", 0): [("A", 0)], ("b", 0): [("B", 0)]},
               [("A", 0), ("B", 0)],
               {TARGET: 1_000_000, ("a", 0): 700_000, ("b", 0): 250_000,
                ("A", 0): 9_000_000, ("B", 0): 9_000_000})
    assert cut_size(g, TARGET) == 2
    carried, routes = flow_capacity(g, TARGET)
    assert carried == 950_000 < g.values[TARGET]
    assert sum(amount for amount, _route in routes) == carried
    assert len(routes) == 2, "valued flow must be decomposed by path, not once per satoshi"


def test_a_narrow_coin_bounds_the_flow_through_it():
    """Capacity is a min cut in satoshis: the tightest coin on the path is what the path delivers."""
    from decluster.disjoint_routes import flow_capacity
    g = valued({TARGET: [("wide", 0)], ("wide", 0): [("narrow", 0)], ("narrow", 0): [("A", 0)]},
               [("A", 0)],
               {TARGET: 500_000, ("wide", 0): 9_000_000, ("narrow", 0): 40_000,
                ("A", 0): 9_000_000})
    assert flow_capacity(g, TARGET)[0] == 40_000


def test_a_coin_with_no_recorded_value_does_not_invent_a_cut():
    """Treating an unknown value as zero would report a separation the graph does not have."""
    from decluster.disjoint_routes import flow_capacity
    g = valued({TARGET: [("unknown", 0)], ("unknown", 0): [("A", 0)]},
               [("A", 0)],
               {TARGET: 100, ("A", 0): 900})          # ("unknown", 0) has no recorded value
    assert flow_capacity(g, TARGET)[0] > 0
