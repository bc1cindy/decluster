import pytest
from decluster import ancestry


def make_fetch(txs):
    def fetch(txid):
        return txs[txid]
    return fetch


def cb_vin():
    return [{"is_coinbase": True, "prevout": None}]


def vin(txid, vout, value):
    return {"is_coinbase": False, "txid": txid, "vout": vout,
            "prevout": {"value": value}}


def test_coinbase_parent_is_absorber():
    # target coin C:0 spent-from tx C, whose single input is coinbase P:0
    txs = {
        "C": {"vin": [vin("P", 0, 5)], "vout": [{"value": 5}]},
        "P": {"vin": cb_vin(), "vout": [{"value": 5}]},
    }
    oracle = lambda i, o: [[1.0]]  # 1 in, 1 out
    g = ancestry.build_extended_graph(("C", 0), depth=6, fetch=make_fetch(txs), link_oracle=oracle)
    dist = ancestry.absorber_distribution(g, ("C", 0))
    assert dist == {("P", 0): 1.0}
    assert g.truncated == 0


def test_depth_cutoff_makes_frontier_absorber():
    txs = {
        "C": {"vin": [vin("P", 0, 5)], "vout": [{"value": 5}]},
        "P": {"vin": [vin("Q", 0, 5)], "vout": [{"value": 5}]},
        "Q": {"vin": cb_vin(), "vout": [{"value": 5}]},
    }
    oracle = lambda i, o: [[1.0]]
    g = ancestry.build_extended_graph(("C", 0), depth=1, fetch=make_fetch(txs), link_oracle=oracle)
    # depth=1: walk C -> P, then P is at the cutoff -> absorber (Q never reached)
    dist = ancestry.absorber_distribution(g, ("C", 0))
    assert dist == {("P", 0): 1.0}


def test_oracle_none_truncates_and_counts():
    txs = {
        "C": {"vin": [vin("P", 0, 3), vin("P", 1, 4)], "vout": [{"value": 7}]},
        "P": {"vin": cb_vin(), "vout": [{"value": 3}, {"value": 4}]},
    }
    # oracle refuses tx C (too big, say): returns None -> C:0 becomes a truncated absorber
    oracle = lambda i, o: None
    g = ancestry.build_extended_graph(("C", 0), depth=6, fetch=make_fetch(txs), link_oracle=oracle)
    assert g.truncated >= 1
    dist = ancestry.absorber_distribution(g, ("C", 0))
    assert dist == {("C", 0): 1.0}  # target itself is the (truncated) absorber


def test_flat_link_splits_provenance():
    # C:0 from tx C with inputs P:0, R:0 (two coinbase origins), flat link 0.5/0.5
    txs = {
        "C": {"vin": [vin("P", 0, 5), vin("R", 0, 5)], "vout": [{"value": 10}]},
        "P": {"vin": cb_vin(), "vout": [{"value": 5}]},
        "R": {"vin": cb_vin(), "vout": [{"value": 5}]},
    }
    oracle = lambda i, o: [[0.5], [0.5]]  # 2 in, 1 out; both inputs equally likely source
    g = ancestry.build_extended_graph(("C", 0), depth=6, fetch=make_fetch(txs), link_oracle=oracle)
    dist = ancestry.absorber_distribution(g, ("C", 0))
    assert dist[("P", 0)] == pytest.approx(0.5)
    assert dist[("R", 0)] == pytest.approx(0.5)


def test_signature_and_truncation_come_from_one_walk():
    """The count is what makes an empty intersection readable, so it has to be
    the same walk the signature came from, not a second one."""
    txs = {
        "C": {"vin": [vin("P", 0, 5), vin("R", 0, 5)], "vout": [{"value": 10}]},
        "P": {"vin": cb_vin(), "vout": [{"value": 5}]},
        "R": {"vin": cb_vin(), "vout": [{"value": 5}]},
    }
    sig, truncated = ancestry.ancestry_signature_and_truncation(
        ("C", 0), depth=6, fetch=make_fetch(txs), link_oracle=lambda i, o: [[0.5], [0.5]]
    )
    assert set(sig) == {("P", 0), ("R", 0)}
    assert truncated.total == 0, "a coinbase boundary is an origin, not a refusal"


def test_an_oracle_refusal_is_counted_as_truncation():
    """A boundary the oracle declined to walk is not an observed origin."""
    txs = {
        "C": {"vin": [vin("P", 0, 3), vin("P", 1, 4)], "vout": [{"value": 7}]},
        "P": {"vin": cb_vin(), "vout": [{"value": 3}, {"value": 4}]},
    }
    sig, truncated = ancestry.ancestry_signature_and_truncation(
        ("C", 0), depth=6, fetch=make_fetch(txs), link_oracle=lambda i, o: None
    )
    assert sig == {("C", 0): 1.0}, "the coin becomes its own boundary"
    assert truncated == ancestry.TruncationSupport(oracle_refused=1, node_capped=0)
    assert truncated.total == 1


def test_a_zero_link_column_is_a_named_boundary_not_an_origin():
    txs = {
        "C": {"vin": [vin("P", 0, 7)], "vout": [{"value": 7}]},
        "P": {"vin": cb_vin(), "vout": [{"value": 7}]},
    }
    sig, support = ancestry.ancestry_signature_and_truncation(
        ("C", 0), depth=6, fetch=make_fetch(txs), link_oracle=lambda i, o: [[0.0]]
    )
    assert sig == {("C", 0): 1.0}
    assert support.zero_link_mass == support.total == 1
    assert support.oracle_refused == support.node_capped == 0


def test_the_two_truncation_causes_are_reported_apart():
    """A capped walk and a refusing oracle are different limits. Collapsed into one count, a
    consumer reading "no view" cannot tell which one it hit — and under the walk's default oracle,
    which refuses only on zero input value, only the cap can fire at all."""
    txs = {
        "C": {"vin": [vin("P", 0, 5)], "vout": [{"value": 5}]},
        "P": {"vin": [vin("Q", 0, 5)], "vout": [{"value": 5}]},
        "Q": {"vin": cb_vin(), "vout": [{"value": 5}]},
    }
    flat = lambda i, o: [[1.0] for _ in i]

    capped = ancestry.build_extended_graph(
        ("C", 0), depth=6, fetch=make_fetch(txs), link_oracle=flat, max_nodes=1
    )
    assert (capped.node_capped, capped.oracle_refused) == (capped.truncated, 0)
    assert capped.truncated > 0

    refused = ancestry.build_extended_graph(
        ("C", 0), depth=6, fetch=make_fetch(txs), link_oracle=lambda i, o: None
    )
    assert (refused.oracle_refused, refused.node_capped) == (refused.truncated, 0)
    assert refused.truncated > 0

    sig, support = ancestry.ancestry_signature_and_truncation(
        ("C", 0), depth=6, fetch=make_fetch(txs), link_oracle=lambda i, o: None
    )
    assert support == ancestry.TruncationSupport(oracle_refused=1, node_capped=0)


def test_a_capped_walk_reports_its_blindness_as_the_cap_not_a_refusal():
    """The default oracle never refuses on width, so a blind default walk is `max_nodes`. The
    support must say so rather than leave the cause to be inferred from the oracle in use."""
    txs = {
        "C": {"vin": [vin("P", 0, 5)], "vout": [{"value": 5}]},
        "P": {"vin": [vin("Q", 0, 5)], "vout": [{"value": 5}]},
        "Q": {"vin": cb_vin(), "vout": [{"value": 5}]},
    }
    g = ancestry.build_extended_graph(
        ("C", 0), depth=6, fetch=make_fetch(txs),
        link_oracle=ancestry.value_flow_link_oracle, max_nodes=1,
    )
    sig = ancestry.absorber_distribution(g, ("C", 0))
    support = ancestry.truncated_support(sig, g)
    assert support.oracle_refused == 0
    assert support.node_capped == support.total == len(sig)


def test_an_unnamed_cause_stays_in_the_total_without_taking_a_name():
    """Keeping an unrecognised cause in the total is right -- under-reporting truncation lets an
    empty intersection read as a refusal. Naming it is not: a consumer branching on the cause would
    act on a walk limit that never fired."""
    from decluster.ancestry import Graph, TruncationSupport, truncated_support

    g = Graph()
    g.truncated_coins = {("odd", 0): "some_future_cause"}
    g.truncated = 1
    support = truncated_support({("odd", 0): 1.0}, g)
    assert support == TruncationSupport(oracle_refused=0, node_capped=0, unattributed=1)
    assert support.total == 1
    assert support.node_capped == 0, "an unknown cause is not the node cap"


def test_an_all_zero_support_is_falsey_like_the_bare_count_it_replaced():
    """`>=` against an int raises, but `if truncated:` would not -- it would silently flip from
    False to True for a caller written against the old bare count."""
    from decluster.ancestry import TruncationSupport

    assert not TruncationSupport(0, 0)
    assert TruncationSupport(0, 1)
    assert TruncationSupport(1, 0)
    assert TruncationSupport(0, 0, unattributed=1)
    assert TruncationSupport(0, 0, zero_link_mass=1)
