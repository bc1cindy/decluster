import sys, os
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.view_match import ViewMatcher, candidate_scores
from decluster.views import PseudonymGraph


def graph(edges):
    g = PseudonymGraph()
    for s, d in edges:
        g._vertex(s), g._vertex(d)
        g.edges[(s, d)] = {"transfers": 1, "value": 1000}
        g._out[s].add(d)
        g._in[d].add(s)
    return g


def relabel(edges, mark="'"):
    return [(s + mark, d + mark) for s, d in edges]


RING = [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"), ("e", "f"), ("f", "a"),
        ("a", "c"), ("b", "d"), ("c", "e"), ("d", "f")]


def test_propagates_a_planted_correspondence_from_a_small_seed():
    ga, gb = graph(RING), graph(relabel(RING))
    out = ViewMatcher(theta=0.0).match(ga, gb, {"a": "a'", "b": "b'"})
    assert len(out) > 2
    assert all(v == k + "'" for k, v in out.items()), out


def test_a_full_seed_is_reproduced_as_the_identity():
    ga, gb = graph(RING), graph(relabel(RING))
    seed = {v: v + "'" for v in ga.vertices}
    assert ViewMatcher().match(ga, gb, seed) == seed


def test_a_vertex_with_no_counterpart_stays_unmatched():
    """The two views need not agree; a vertex absent from the other graph is meant to be
    left alone rather than forced onto the nearest thing."""
    ga = graph(RING + [("a", "orphan")])
    gb = graph(relabel(RING))
    out = ViewMatcher(theta=0.0).match(ga, gb, {"a": "a'", "b": "b'"})
    assert "orphan" not in out


def test_a_dst_vertex_is_claimed_at_most_once():
    ga, gb = graph(RING), graph(relabel(RING))
    out = ViewMatcher(theta=0.0).match(ga, gb, {"a": "a'", "b": "b'"})
    assert len(set(out.values())) == len(out)


def test_reversibility_rejects_a_match_that_loses_from_the_other_side():
    """`c` is the natural image of both `x` and `y`; without the reverse check whichever is
    visited first claims it."""
    ga = graph([("s", "x"), ("s", "y"), ("x", "y")])
    gb = graph([("s'", "c"), ("s'", "d"), ("c", "d")])
    strict = ViewMatcher(theta=0.0, reversible=True).match(ga, gb, {"s": "s'"})
    loose = ViewMatcher(theta=0.0, reversible=False).match(ga, gb, {"s": "s'"})
    assert len(strict) <= len(loose)


def test_the_hub_cap_stops_propagation_routing_through_a_hub():
    """A hub is adjacent to everything, so it votes for every candidate. Above the cap its
    evidence must be ignored entirely, not merely down-weighted."""
    hub_edges = [("h", f"n{i}") for i in range(30)]
    ga, gb = graph(hub_edges), graph(relabel(hub_edges))
    seed = {"h": "h'"}
    assert candidate_scores("n0", ga, gb, seed, hubcap=100) != Counter()
    assert candidate_scores("n0", ga, gb, seed, hubcap=5) == Counter()


def test_a_diffuse_tie_is_refused():
    """Two candidates equally supported carry no information; the eccentricity gate must
    decline rather than pick one."""
    ga = graph([("s", "u"), ("s", "t")])
    gb = graph([("s'", "p"), ("s'", "q")])
    out = ViewMatcher(theta=5.0).match(ga, gb, {"s": "s'"})
    assert set(out) == {"s"}


def test_damping_discounts_evidence_from_a_popular_neighbour():
    edges = [("m", "a"), ("m", "b")] + [("m", f"x{i}") for i in range(20)]
    ga, gb = graph(edges), graph(relabel(edges))
    seed = {"m": "m'"}
    hot = candidate_scores("a", ga, gb, seed, hubcap=100, damping=True)
    flat = candidate_scores("a", ga, gb, seed, hubcap=100, damping=False)
    assert max(hot.values()) < max(flat.values())


def test_an_unmatched_neighbourhood_scores_nothing():
    ga, gb = graph(RING), graph(relabel(RING))
    assert candidate_scores("a", ga, gb, {}) == Counter()


def test_stat_overrides_the_graph_degree_for_damping_and_the_hub_cap():
    """Both guards read connectedness, so they must be able to read it from the *unfiltered*
    graph. Dropping leaves to fit a wide view in memory otherwise lowers the degree of
    everything they hung off and silently reweights every score."""
    edges = [("m", "a"), ("m", "b")]
    ga, gb = graph(edges), graph(relabel(edges))
    seed = {"m": "m'"}
    lean = candidate_scores("a", ga, gb, seed, hubcap=100)
    as_if_full = candidate_scores("a", ga, gb, seed, hubcap=100, stat={"m'": 64})
    assert max(as_if_full.values()) < max(lean.values())        # damped as the full degree
    assert candidate_scores("a", ga, gb, seed, hubcap=100, stat={"m'": 400}) == Counter()
    assert candidate_scores("a", ga, gb, seed, hubcap=500, stat={"m'": 400}) != Counter()


def test_confidence_is_recorded_per_match_and_ranks_a_clear_win_above_a_close_one():
    """The framework locates the value in the *high confidence* links rather than in
    coverage, so a match that barely cleared the gate must be distinguishable from one that
    won outright."""
    ga, gb = graph(RING), graph(relabel(RING))
    m = ViewMatcher(theta=0.0)
    out = m.match(ga, gb, {"a": "a'", "b": "b'"})
    assert set(m.confidence) == set(out) - {"a", "b"}
    assert all(ecc > 0 and sc > 0 for ecc, sc in m.confidence.values())


def test_an_unopposed_candidate_reads_as_maximally_confident():
    """A single candidate has no runner-up to be separated from, so eccentricity is
    undefined; it must read as certain rather than as zero, which would sort it last."""
    ga, gb = graph([("s", "x")]), graph([("s'", "x'")])
    m = ViewMatcher(theta=0.5)
    m.match(ga, gb, {"s": "s'"})
    assert m.confidence["x"][0] == float("inf")


# --- attributes as conditioners ---------------------------------------------

def test_agreement_counts_matching_axes_and_abstains_when_a_signature_is_missing():
    from decluster.view_match import agreement
    assert agreement(("a", "b", "c"), ("a", "b", "c")) == 1.0
    assert agreement(("a", "b", "c"), ("a", "x", "y")) == 1 / 3
    assert agreement(("a",), None) is None and agreement(None, ("a",)) is None
    assert agreement(("a", "b"), ("a",)) is None


def test_the_conditioner_is_bounded_and_neutral_at_half_agreement():
    """An attribute may promote or demote a candidate that structure already found. It must
    never manufacture one, so the factor is bounded and zero score stays zero."""
    from decluster.view_match import _condition
    assert _condition(10.0, 0.5, 0.4) == 10.0
    assert _condition(10.0, 1.0, 0.4) == 14.0
    assert _condition(10.0, 0.0, 0.4) == 6.0
    assert _condition(0.0, 1.0, 0.4) == 0.0
    assert _condition(10.0, None, 0.4) == 10.0


def test_edge_signature_agreement_reorders_candidates():
    """Two candidates equally supported by structure; the one whose edge to the matched
    neighbour looks like the reference edge must win."""
    from decluster.views import contract

    def tx(a, b, version=2, txid="t"):
        return {"txid": txid, "height": 1, "version": version, "locktime": 0,
                "fee": 100, "weight": 400,
                "vin": [{"txid": "p" + a, "vout": 0, "sequence": 0xFFFFFFFF,
                         "prevout": {"value": 1000, "scriptpubkey_type": "v0_p2wpkh",
                                     "scriptpubkey_address": a}}],
                "vout": [{"value": 500, "scriptpubkey_type": "v0_p2wpkh",
                          "scriptpubkey_address": b}]}

    sa = [(tx("u", "m", version=2), None)]
    sb = [(tx("good", "m'", version=2), None), (tx("bad", "m'", version=1), None)]
    ga = contract(sa, [0], {})
    gb = contract(sb, [0, 1], {})
    flat = candidate_scores("u", ga, gb, {"m": "m'"}, edge_alpha=0.0)
    cond = candidate_scores("u", ga, gb, {"m": "m'"}, edge_alpha=0.5)
    assert flat["good"] == flat["bad"]                    # structure alone cannot separate
    assert cond["good"] > cond["bad"]                     # the edge attribute can


def test_attributes_are_off_by_default():
    """The conditioners change scores, so they must be opt-in rather than silently on."""
    m = ViewMatcher()
    assert m.edge_alpha == 0.0 and m.vertex_alpha == 0.0
