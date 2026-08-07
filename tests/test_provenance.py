import pytest
from decluster.provenance import (
    candidate_coins,
    descended_inputs,
    funding_txids,
    overlap_share,
    rank_by_overlap,
)


def _tx(txid, parents, outs=()):
    """parents: [(funder_txid, vout, value|None)]"""
    return {
        "txid": txid,
        "vin": [
            {
                "txid": p,
                "vout": n,
                **(
                    {"prevout": {"value": v, "scriptpubkey_type": "v0_p2wpkh"}}
                    if v is not None
                    else {}
                ),
            }
            for p, n, v in parents
        ],
        "vout": [{"value": v} for v in outs],
    }


def test_funding_txids_dedupes_repeated_parents():
    tx = _tx("t", [("a", 0, 1), ("a", 1, 2), ("b", 0, 3)])
    assert funding_txids(tx) == {"a", "b"}


def test_descended_inputs_reports_position_and_value():
    tx = _tx("t", [("a", 0, 100), ("z", 0, 200), ("a", 3, 300)])
    assert descended_inputs(tx, {"a"}) == [(0, "a", 0, 100), (2, "a", 3, 300)]


def test_descended_inputs_keeps_unresolved_prevouts_as_none():
    tx = _tx("t", [("a", 0, None)])
    assert descended_inputs(tx, {"a"}) == [(0, "a", 0, None)]


def test_overlap_share_is_the_input_fraction():
    tx = _tx("t", [("a", 0, 1), ("z", 0, 1), ("z", 1, 1), ("a", 1, 1)])
    assert overlap_share(tx, {"a"}) == 0.5
    assert overlap_share(tx, {"q"}) == 0.0
    assert overlap_share({"vin": []}, {"a"}) == 0.0


def test_rank_by_overlap_separates_a_joined_round_from_background():
    joined = _tx("joined", [("a", i, 1) for i in range(7)] + [("z", 0, 1)])
    background = _tx("bg", [("a", 0, 1)] + [("z", i, 1) for i in range(9)])
    rows = rank_by_overlap([background, joined], {"a"})
    assert [r[0] for r in rows] == ["joined", "bg"]
    assert rows[0][1] == 7 and rows[0][2] == 8
    assert rows[1][3] == 0.1


def test_candidate_coins_drops_one_copy_of_the_anchor():
    tx = _tx("t", [("a", 0, 500), ("a", 1, 500), ("a", 2, 100), ("z", 0, 900)])
    # one 500 is the anchor; the other 500 stays a candidate
    assert candidate_coins(tx, {"a"}, anchor_value=500) == [
        (500, "v0_p2wpkh", 1),
        (100, "v0_p2wpkh", 1),
    ]


def test_candidate_coins_without_anchor_keeps_everything_descended():
    tx = _tx("t", [("a", 0, 500), ("a", 1, 100)])
    assert candidate_coins(tx, {"a"}) == [(500, "v0_p2wpkh", 1), (100, "v0_p2wpkh", 1)]


def test_candidate_coins_drops_unvalued_inputs():
    tx = _tx("t", [("a", 0, None), ("a", 1, 100)])
    assert candidate_coins(tx, {"a"}) == [(100, "v0_p2wpkh", 1)]


def test_candidate_coins_ignores_an_absent_anchor():
    tx = _tx("t", [("a", 0, 100)])
    assert candidate_coins(tx, {"a"}, anchor_value=999) == [(100, "v0_p2wpkh", 1)]




def test_overlap_ranks_by_coin_flow_not_by_value_share():
    """RESULTS-provenance.md: the measure counts inputs that descend, so a
    participant holding little of a round's value can still rank high on it, and
    one holding most of it can rank low. That is why it does not substitute for
    the conservation bound, which reads value."""
    # child A: many small coins descend from the parent; the parent's owner holds
    # a trivial share of A's value.
    a = {"vin": [{"txid": "P", "prevout": {"value": 1}} for _ in range(8)]
                + [{"txid": "Q", "prevout": {"value": 1000}} for _ in range(2)]}
    # child B: one huge coin descends; the owner holds most of B's value.
    b = {"vin": [{"txid": "P", "prevout": {"value": 10_000}}]
                + [{"txid": "Q", "prevout": {"value": 1}} for _ in range(9)]}
    assert overlap_share(a, {"P"}) == pytest.approx(0.8)
    assert overlap_share(b, {"P"}) == pytest.approx(0.1)


def test_a_common_parent_is_not_evidence_on_its_own():
    """The measured population has 11% of coinjoin pairs overlapping, so a single
    descended input is the ordinary case, not a signal."""
    tx = {"vin": [{"txid": "P", "prevout": {"value": 1}}]
                 + [{"txid": f"X{i}", "prevout": {"value": 1}} for i in range(453)]}
    assert overlap_share(tx, {"P"}) == pytest.approx(1 / 454, abs=1e-6)
