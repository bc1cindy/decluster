"""Cluster-lift (intersect wallets, not coins; cit-42) and cross-event accumulation."""
import math
import pytest

from decluster.intersect import shared_origins, accumulate_intersections


def test_cluster_lift_intersects_wallets_not_coins():
    # two branches sharing no COIN-origin, but whose coins belong to the same wallet W
    s1, s2 = {"coinA": 1.0}, {"coinB": 1.0}
    assert shared_origins([s1, s2]) == []                        # coin-level: no overlap
    lifted = shared_origins([s1, s2], cluster_of={"coinA": "W", "coinB": "W"})
    assert [a for a, _, _ in lifted] == ["W"]                    # wallet-level: they meet at W


def test_cluster_lift_requires_population_rarity_in_the_cluster_space():
    sigs = [{"a1": 1.0, "hub1": 1.0}, {"a2": 1.0, "hub2": 1.0}]
    clusters = {"a1": "rare", "a2": "rare", "hub1": "hub", "hub2": "hub"}
    with pytest.raises(ValueError, match="cluster_rarity"):
        shared_origins(sigs, rarity={"a1": 10}, cluster_of=clusters)
    got = shared_origins(sigs, rarity={"a1": 10}, cluster_of=clusters,
                         cluster_rarity={"rare": 2, "hub": 1023})
    weights = {a: w for a, _m, w in got}
    assert weights["rare"] == pytest.approx(1.0 / math.log2(3))
    assert weights["hub"] < 0.2


def test_accumulation_narrows_across_observations():
    # each observation's shared origins; the surviving set shrinks as observations accumulate
    obs = [[{"x": 1.0, "y": 1.0, "z": 1.0}, {"x": 1.0, "y": 1.0, "z": 1.0}],  # {x,y,z}
           [{"x": 1.0, "y": 1.0}, {"x": 1.0, "y": 1.0}],                      # {x,y}
           [{"x": 1.0}, {"x": 1.0}]]                                         # {x}
    surviving, bits = accumulate_intersections(obs)
    assert surviving == {"x"}                                     # converged to one origin
    assert bits > 0                                              # narrowing recorded in bits


def test_accumulation_can_include_the_first_observation_from_a_known_universe():
    obs = [[{"x": 1.0, "y": 1.0}, {"x": 1.0, "y": 1.0}]]
    _surviving, relative = accumulate_intersections(obs)
    _surviving, absolute = accumulate_intersections(obs, universe_size=8)
    assert relative == 0.0
    assert absolute == 2.0


def test_an_unknown_coin_never_collapses_into_a_shared_pseudo_cluster():
    """A callable cluster map answering None for a coin it does not know must fall back to the
    coin, exactly as the dict form does. Collapsing every unclustered origin onto one key makes
    branches with nothing in common intersect at full mass — a fabricated attribution."""
    s1, s2 = {"coinA": 1.0}, {"coinB": 1.0}
    assert shared_origins([s1, s2], cluster_of={}) == []
    assert shared_origins([s1, s2], cluster_of=lambda a: None) == []


def test_evaluate_intersects_wallets_when_given_a_cluster_map():
    """The writeup's core move: candidate origins are clusters, so two branches overlap without
    their origin coins being connected on the transaction graph."""
    from decluster.intersect import evaluate
    sigs = {("t", 0): {"c1": 1.0}, ("t", 1): {"c2": 1.0}}
    cand = {"txid": "j", "outpoints": [("t", 0), ("t", 1)]}

    coin_level = evaluate(cand, sigs.__getitem__)
    assert coin_level["shared"] == []                      # different coins: no overlap

    lifted = evaluate(cand, sigs.__getitem__, cluster_of={"c1": "W", "c2": "W"})
    assert [a for a, _, _ in lifted["shared"]] == ["W"]    # one wallet held both
    assert lifted["sizes"] == [1, 1]                       # sizes are wallets, not coins


def test_evaluate_refuses_to_weight_a_lifted_intersection_on_coin_support():
    from decluster.intersect import evaluate
    sigs = {("t", 0): {"c1": 1.0}, ("t", 1): {"c1": 1.0}}
    cand = {"txid": "j", "outpoints": [("t", 0), ("t", 1)]}
    with pytest.raises(ValueError, match="cluster_rarity"):
        evaluate(cand, sigs.__getitem__, rarity={"c1": 10}, cluster_of={"c1": "W"})


def test_cluster_rarity_is_recounted_over_the_population_after_lifting():
    """Coin support does not survive coarsening: a wallet holding many coins would inherit the
    support of the rarest of them."""
    from decluster.propagate import build_cluster_rarity
    corpus = [{"c1": 1.0}, {"c2": 1.0}, {"c3": 1.0}]
    cluster_of = {"c1": "W", "c2": "W", "c3": "V"}
    assert build_cluster_rarity(corpus, cluster_of) == {"W": 2, "V": 1}
    # an unclustered coin keeps its own identity rather than joining a None bucket
    assert build_cluster_rarity([{"c1": 1.0}, {"zz": 1.0}], lambda a: None) == {"c1": 1, "zz": 1}
