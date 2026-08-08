import math

import pytest

from decluster import ancestry, path_count


def make_fetch(txs):
    def fetch(txid):
        return txs[txid]
    return fetch


def cb_vin():
    return [{"is_coinbase": True, "prevout": None}]


def vin(txid, vout, value):
    return {"is_coinbase": False, "txid": txid, "vout": vout,
            "prevout": {"value": value}}


def count_report(log_w, count=None):
    if log_w is None:
        return {"kind": "unknown", "count": None, "log_w": None}
    return {"kind": "exact", "count": count, "log_w": log_w}


# --- fixture 1: known 2-hop DAG, hand-checked multiplicities -----------------
#
# C:0 --0.6--> P:0 --0.7--> Q:0 (coinbase)
#      --0.4--> P:1 --0.5--> Q:0
#                     --0.3--> R:0 (coinbase)
#                     --0.5--> R:0
# W(E): tx C = 5, tx P = 3.
#
# hand computation (see task-3 derivation):
#   mult(P:0) = 0.6*5 = 3.0        mult(P:1) = 0.4*5 = 2.0
#   mult(Q:0) = 3.0*0.7*3 + 2.0*0.5*3 = 6.3 + 3.0 = 9.3
#   mult(R:0) = 3.0*0.3*3 + 2.0*0.5*3 = 2.7 + 3.0 = 5.7
#   W_paths = 15.0 -> Q:0 weight 0.62, R:0 weight 0.38

def _two_hop_dag_fixture():
    txs = {
        "C": {"vin": [vin("P", 0, 3), vin("P", 1, 4)], "vout": [{"value": 7}]},
        "P": {"vin": [vin("Q", 0, 2), vin("R", 0, 5)],
              "vout": [{"value": 2}, {"value": 5}]},
        "Q": {"vin": cb_vin(), "vout": [{"value": 2}]},
        "R": {"vin": cb_vin(), "vout": [{"value": 5}]},
    }

    def link_oracle(in_vals, out_vals):
        if in_vals == [3, 4]:
            return [[0.6], [0.4]]
        if in_vals == [2, 5]:
            return [[0.7, 0.5], [0.3, 0.5]]
        return None

    def count_oracle(in_vals, out_vals):
        if in_vals == [3, 4]:
            return count_report(math.log(5), count=5)
        if in_vals == [2, 5]:
            return count_report(math.log(3), count=3)
        return count_report(None)

    return txs, link_oracle, count_oracle


def test_known_two_hop_dag_matches_hand_computation():
    txs, link_oracle, count_oracle = _two_hop_dag_fixture()
    res = path_count.path_count_anonymity(
        ("C", 0), depth=6, fetch=make_fetch(txs),
        link_oracle=link_oracle, count_oracle=count_oracle)

    assert res["origins_weighted"].keys() == {("Q", 0), ("R", 0)}
    assert res["origins_weighted"][("Q", 0)] == pytest.approx(0.62)
    assert res["origins_weighted"][("R", 0)] == pytest.approx(0.38)
    assert res["log_W_paths"] == pytest.approx(math.log(15.0))
    assert res["min_entropy"] == pytest.approx(-math.log2(0.62))
    assert res["shannon"] == pytest.approx(
        -(0.62 * math.log2(0.62) + 0.38 * math.log2(0.38)))
    assert res["truncated"] == 0


def test_multiplicity_upweights_higher_w_e_origin():
    # T:0 splits 0.5/0.5 (equal under plain link-prob absorption) into P:0 and
    # Q:0, each a single-input pass-through to a coinbase origin. Under §04
    # (link-probability only) the two origins are exactly tied at 0.5/0.5.
    # W(E): tx P = 10 (highly ambiguous), tx Q = 2 (much less ambiguous) ->
    # path-count must break the tie in O_P's favor.
    txs = {
        "T": {"vin": [vin("P", 0, 1), vin("Q", 0, 1)], "vout": [{"value": 2}]},
        "P": {"vin": [vin("OP", 0, 1)], "vout": [{"value": 1}]},
        "Q": {"vin": [vin("OQ", 0, 1)], "vout": [{"value": 1}]},
        "OP": {"vin": cb_vin(), "vout": [{"value": 1}]},
        "OQ": {"vin": cb_vin(), "vout": [{"value": 1}]},
    }

    def link_oracle(in_vals, out_vals):
        if len(in_vals) == 2:
            return [[0.5], [0.5]]
        return [[1.0]]

    # values alone can't tell tx P and tx Q apart (both single-input
    # pass-throughs of value 1), so dispatch W(E) by the txid the walk is
    # currently fetching: a stateful fetch records it for count_oracle to read.
    log_w_by_txid = {"T": math.log(5), "P": math.log(10), "Q": math.log(2)}
    last_txid = {}

    def fetch(txid):
        last_txid["v"] = txid
        return txs[txid]

    def count_oracle(in_vals, out_vals):
        return count_report(log_w_by_txid.get(last_txid["v"]))

    g = ancestry.build_extended_graph(
        ("T", 0), depth=6, fetch=fetch, link_oracle=link_oracle)
    dist04 = ancestry.absorber_distribution(g, ("T", 0))
    assert dist04[("OP", 0)] == pytest.approx(0.5)
    assert dist04[("OQ", 0)] == pytest.approx(0.5)

    res = path_count.path_count_anonymity(
        ("T", 0), depth=6, fetch=fetch,
        link_oracle=link_oracle, count_oracle=count_oracle)

    assert res["origins_weighted"][("OP", 0)] > dist04[("OP", 0)]
    assert res["origins_weighted"][("OQ", 0)] < dist04[("OQ", 0)]
    assert res["origins_weighted"][("OP", 0)] == pytest.approx(25 / 30)
    assert res["origins_weighted"][("OQ", 0)] == pytest.approx(5 / 30)


def test_w_e_none_falls_back_to_link_prob_only():
    # tx P's count_oracle refuses (log_w=None) -> that hop's multiplicity
    # factor is 1 (link-prob weight alone), never a fabricated count.
    txs, link_oracle, _ = _two_hop_dag_fixture()

    def count_oracle(in_vals, out_vals):
        if in_vals == [3, 4]:
            return count_report(math.log(5), count=5)
        return count_report(None)  # tx P: off-regime, no count

    res = path_count.path_count_anonymity(
        ("C", 0), depth=6, fetch=make_fetch(txs),
        link_oracle=link_oracle, count_oracle=count_oracle)

    # mult(P:0)=3.0, mult(P:1)=2.0 as before (tx C's W(E) still applies);
    # tx P falls back to factor 1: mult(Q:0)=3.0*0.7 + 2.0*0.5=3.1,
    # mult(R:0)=3.0*0.3 + 2.0*0.5=1.9, W_paths=5.0
    assert res["origins_weighted"][("Q", 0)] == pytest.approx(3.1 / 5.0)
    assert res["origins_weighted"][("R", 0)] == pytest.approx(1.9 / 5.0)
    assert res["truncated"] == 0


def _binary_tree_fetch(max_len):
    """Full binary ancestry tree (mirrors test_ancestry.py's fixture): each non-coinbase coin has
    2 inputs, keyed by the txid's bit-path; coinbase once the path reaches max_len. max_len=3 has
    8 leaf origins -- more than a small max_nodes cap can reach without collapsing some into a
    truncation atom."""
    def fetch(txid):
        if len(txid) >= max_len:
            return {"vin": [{"is_coinbase": True}], "vout": [{"value": 100}]}
        left, right = txid + "0", txid + "1"
        return {"vin": [{"txid": left, "vout": 0, "prevout": {"value": 100}},
                        {"txid": right, "vout": 0, "prevout": {"value": 100}}],
                "vout": [{"value": 200}]}
    return fetch


_tree_link_oracle = lambda ins, outs: [[1.0] * len(outs) for _ in ins]
_tree_count_oracle = lambda ins, outs: count_report(math.log(2), count=2)  # uniform W(E)=2


def test_max_nodes_bounds_walk_without_error():
    fetch = _binary_tree_fetch(max_len=3)
    res_full = path_count.path_count_anonymity(
        ("", 0), depth=8, fetch=fetch,
        link_oracle=_tree_link_oracle, count_oracle=_tree_count_oracle)
    res_capped = path_count.path_count_anonymity(
        ("", 0), depth=8, max_nodes=6, fetch=fetch,
        link_oracle=_tree_link_oracle, count_oracle=_tree_count_oracle)

    assert res_capped["truncated"] > 0
    # capping mid-tree collapses some multi-leaf subtrees into a single truncation atom
    assert len(res_capped["origins_weighted"]) < len(res_full["origins_weighted"])
    total = sum(res_capped["origins_weighted"].values())
    assert total == pytest.approx(1.0)
