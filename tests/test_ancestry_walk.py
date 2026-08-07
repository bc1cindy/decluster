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
    assert truncated == 0, "a coinbase boundary is an origin, not a refusal"


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
    assert truncated == 1
