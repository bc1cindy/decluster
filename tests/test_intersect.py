import pytest
from decluster.intersect import evaluate, rarity_weight, score_candidate, shared_origins


def test_rarity_weight_discounts_a_hub_and_keeps_a_rare_origin():
    assert rarity_weight("rare", None) == 1.0
    assert rarity_weight("rare", {"rare": 1}) == 1.0
    hub = rarity_weight("hub", {"hub": 1023})
    assert 0.0 < hub < 0.2, hub


def test_shared_origins_keeps_only_what_every_branch_carries():
    a = {"red": 0.6, "green": 0.4}
    b = {"red": 0.5, "blue": 0.5}
    assert [x[0] for x in shared_origins([a, b])] == ["red"]


def test_shared_origins_takes_the_weakest_branch_mass():
    a = {"red": 0.6}
    b = {"red": 0.2}
    assert shared_origins([a, b])[0][1] == 0.2


def test_shared_origins_is_empty_when_branches_share_nothing():
    assert shared_origins([{"red": 1.0}, {"blue": 1.0}]) == []
    assert shared_origins([]) == []
    assert shared_origins([{"red": 1.0}, {}]) == []


def test_shared_origins_orders_by_weighted_mass():
    a = {"hub": 0.9, "rare": 0.3}
    b = {"hub": 0.9, "rare": 0.3}
    rarity = {"hub": 4095, "rare": 1}
    assert [x[0] for x in shared_origins([a, b], rarity)] == ["rare", "hub"]


def test_evaluate_reports_how_much_the_intersection_removed():
    sigs = {
        ("t", 0): {"red": 0.5, "green": 0.5},
        ("t", 1): {"red": 0.5, "blue": 0.5},
    }
    candidate = {"txid": "join", "outpoints": [("t", 0), ("t", 1)]}
    got = evaluate(candidate, sigs.__getitem__)
    assert got["txid"] == "join"
    assert got["branches"] == 2
    assert got["sizes"] == [2, 2]
    assert [x[0] for x in got["shared"]] == ["red"]
    assert got["collapsed"] == 1


def test_evaluate_reports_zero_collapse_when_the_cospend_adds_nothing():
    sigs = {("t", 0): {"red": 1.0}, ("t", 1): {"red": 1.0}}
    got = evaluate({"txid": "j", "outpoints": [("t", 0), ("t", 1)]}, sigs.__getitem__)
    assert got["collapsed"] == 0
    assert [x[0] for x in got["shared"]] == ["red"]


def test_evaluate_never_claims_to_have_scored_the_cospend():
    """The seam: adjudicating the co-spend is `cluster_refined`'s job, not this."""
    sigs = {("t", 0): {"red": 1.0}, ("t", 1): {"red": 1.0}}
    got = evaluate({"txid": "j", "outpoints": [("t", 0), ("t", 1)]}, sigs.__getitem__)
    assert got["scored"] is False


def test_evaluate_on_disjoint_branches_refuses_a_common_origin():
    sigs = {("t", 0): {"red": 1.0}, ("t", 1): {"blue": 1.0}}
    got = evaluate({"txid": "j", "outpoints": [("t", 0), ("t", 1)]}, sigs.__getitem__)
    assert got["shared"] == []
    assert got["collapsed"] == 1


def test_the_monitor_output_feeds_this_module_unchanged():
    """The seam that makes the three modules one pipeline rather than three parts."""
    from decluster.monitor import walk_frontier

    txs = {"a": {"vin": [{}], "vout": [{}, {}]}, "join": {"vin": [{}, {}], "vout": [{}]}}
    spends = {
        "a": [{"spent": True, "txid": "join"}, {"spent": True, "txid": "join"}],
        "join": [{"spent": False}],
    }
    walked = walk_frontier(
        [("a", 0), ("a", 1)], txs.__getitem__, lambda t: spends.get(t, [])
    )
    assert len(walked["candidates"]) == 1

    sigs = {("a", 0): {"red": 0.5, "green": 0.5}, ("a", 1): {"red": 0.5, "blue": 0.5}}
    got = evaluate(walked["candidates"][0], sigs.__getitem__)
    assert got["txid"] == "join"
    assert [x[0] for x in got["shared"]] == ["red"]
    assert got["collapsed"] == 1


def _funder(op):
    return op[0]


def test_score_candidate_believes_a_cospend_the_engine_keeps_together():
    candidate = {"txid": "j", "outpoints": [("a", 0), ("b", 0)]}
    cluster_fn = lambda nodes, sigs=None: ([{"a", "b"}], [], [])
    got = score_candidate(candidate, cluster_fn, _funder)
    assert got["believed"] is True
    assert got["refused_pairs"] == []


def test_score_candidate_does_not_believe_a_cospend_the_engine_refused():
    """The case the engine exists for: a merge the co-spend alone would have made."""
    candidate = {"txid": "j", "outpoints": [("a", 0), ("b", 0)]}
    refused = [("a", "b", "t", -5.0, 0.0, -5.0)]
    cluster_fn = lambda nodes, sigs=None: ([{"a"}, {"b"}], refused, [])
    got = score_candidate(candidate, cluster_fn, _funder)
    assert got["believed"] is False
    assert got["refused_pairs"] == refused


def test_score_candidate_does_not_believe_branches_left_in_separate_groups():
    candidate = {"txid": "j", "outpoints": [("a", 0), ("b", 0)]}
    cluster_fn = lambda nodes, sigs=None: ([{"a"}, {"b"}], [], [])
    assert score_candidate(candidate, cluster_fn, _funder)["believed"] is False


def test_score_candidate_ignores_refusals_between_unrelated_nodes():
    candidate = {"txid": "j", "outpoints": [("a", 0), ("b", 0)]}
    refused = [("c", "d", "t", -5.0, 0.0, -5.0)]
    cluster_fn = lambda nodes, sigs=None: ([{"a", "b"}, {"c"}, {"d"}], refused, [])
    got = score_candidate(candidate, cluster_fn, _funder)
    assert got["believed"] is True
    assert got["refused_pairs"] == []


def test_the_narrowing_is_reported_in_bits_as_well_as_origins():
    """Bits are the repository's currency; a raw count is not comparable across
    branches of different sizes."""
    from decluster.intersect import collapse_bits

    assert collapse_bits(8, 2) == 2.0        # eight origins down to two
    assert collapse_bits(4, 4) == 0.0        # the co-spend told us nothing
    assert collapse_bits(0, 0) is None       # no signatures at all


def test_an_empty_intersection_reports_no_bits():
    """An empty intersection refuses the reading that the branches share an
    origin. Reporting it as infinite narrowing would invert that."""
    from decluster.intersect import collapse_bits, evaluate

    assert collapse_bits(5, 0) is None
    out = evaluate(
        {"txid": "t", "outpoints": [("a", 0), ("b", 0)]},
        {("a", 0): {"red": 1.0}, ("b", 0): {"blue": 1.0}}.__getitem__,
    )
    assert out["shared"] == []
    assert out["collapsed_bits"] is None


def test_evaluate_reports_the_bits_alongside_the_count():
    sigs = {
        ("a", 0): {"red": 0.5, "green": 0.3, "blue": 0.2, "grey": 0.1},
        ("b", 0): {"red": 0.5, "green": 0.4, "pink": 0.1},
    }
    out = evaluate({"txid": "t", "outpoints": [("a", 0), ("b", 0)]}, sigs.__getitem__)
    assert [a for a, _, _ in out["shared"]] == ["red", "green"]
    assert out["collapsed"] == 1                    # smallest branch had 3
    assert out["collapsed_bits"] == pytest.approx(0.5849625007)


def test_signatures_reach_the_engine_rekeyed_by_funder():
    """The walk tracks coins, the engine partitions transactions, so the
    per-coin signatures have to be re-keyed before the provenance channel can
    read them."""
    seen = {}

    def cluster_fn(nodes, sigs=None):
        seen["sigs"] = sigs
        return ([set(nodes)], [], [])

    score_candidate(
        {"txid": "join", "outpoints": [("a", 0), ("b", 1)]},
        cluster_fn,
        lambda op: op[0],
        signatures={("a", 0): {"red": 1.0}, ("b", 1): {"blue": 1.0}},
    )
    assert seen["sigs"] == {"a": {"red": 1.0}, "b": {"blue": 1.0}}


def test_the_engine_is_left_dark_when_no_signatures_are_supplied():
    """Absent evidence is absent, not guessed: the channel gets None."""
    seen = {}

    def cluster_fn(nodes, sigs=None):
        seen["sigs"] = sigs
        return ([set(nodes)], [], [])

    score_candidate({"txid": "j", "outpoints": [("a", 0)]}, cluster_fn, lambda op: op[0])
    assert seen["sigs"] is None


def test_a_blind_branch_is_flagged_so_an_empty_intersection_is_not_read_as_refusal():
    """A boundary that is entirely truncation contains no observed origin, so the
    branches fail to overlap whatever their provenance is."""
    cand = {"txid": "t", "outpoints": [("a", 0), ("b", 0)]}
    sigs = {("a", 0): {"x": 0.5, "y": 0.5}, ("b", 0): {"p": 1.0}}
    out = evaluate(cand, sigs.__getitem__, truncation_of={("a", 0): 2, ("b", 0): 0}.__getitem__)
    assert out["shared"] == []
    assert out["truncated"] == [2, 0]
    assert out["blind"] is True, "branch a sees nothing but the oracle refusing"


def test_an_empty_intersection_with_real_boundaries_is_not_blind():
    cand = {"txid": "t", "outpoints": [("a", 0), ("b", 0)]}
    sigs = {("a", 0): {"x": 0.5, "y": 0.5}, ("b", 0): {"p": 1.0}}
    out = evaluate(cand, sigs.__getitem__, truncation_of={("a", 0): 0, ("b", 0): 0}.__getitem__)
    assert out["shared"] == [] and out["blind"] is False


def test_truncation_is_absent_rather_than_assumed_when_not_supplied():
    out = evaluate({"txid": "t", "outpoints": [("a", 0)]}, lambda op: {"x": 1.0})
    assert out["truncated"] is None and out["blind"] is False
