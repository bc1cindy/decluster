import math

import pytest

from decluster import path_count


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
    assert res["min_entropy"] == pytest.approx(-math.log2(0.62))
    assert res["shannon"] == pytest.approx(
        -(0.62 * math.log2(0.62) + 0.38 * math.log2(0.38)))
    assert res["truncated"] == 0


def test_count_oracle_is_accepted_but_has_no_effect_on_the_result():
    # `count_oracle` is kept only for backward compatibility with callers that still pass one
    # (see the module docstring): whether it returns a real count or refuses, the weighting is
    # link probability alone, so the result on this fixture is identical either way.
    txs, link_oracle, real_count_oracle = _two_hop_dag_fixture()

    def refusing_count_oracle(in_vals, out_vals):
        return count_report(None)

    with_counts = path_count.path_count_anonymity(
        ("C", 0), depth=6, fetch=make_fetch(txs),
        link_oracle=link_oracle, count_oracle=real_count_oracle)
    without_counts = path_count.path_count_anonymity(
        ("C", 0), depth=6, fetch=make_fetch(txs),
        link_oracle=link_oracle, count_oracle=refusing_count_oracle)

    assert with_counts["origins_weighted"] == without_counts["origins_weighted"]


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


def test_the_saddle_point_estimate_is_refused_rather_than_multiplied_in():
    """The path count is a lower bound only if every W(E) in it is one. The Sasamoto tier is an
    approximation in both directions, so an over-estimate would credit a coin with counterfactual
    paths the transaction may not admit — privacy the holder does not have."""
    from decluster.counting import guaranteed_log_w
    assert guaranteed_log_w({"kind": "exact", "log_w": 2.0}) == 2.0
    assert guaranteed_log_w({"kind": "LowerBound", "log_w": 2.0}) == 2.0
    assert guaranteed_log_w({"kind": "lower_bound", "log_w": 2.0}) == 2.0
    assert guaranteed_log_w({"kind": "LogApprox", "log_w": 2.0}) is None
    assert guaranteed_log_w({"kind": "unknown", "log_w": None}) is None
    assert guaranteed_log_w({"log_w": 2.0}) is None          # no tier declared: refuse


# P and Q differ in VALUE, so the count oracle can tell them apart. Without that the factor is
# symmetric and cancels in the normalisation, and the test passes against the unfixed module.
_AB_TXS = {
    "T":  {"vin": [vin("P", 0, 1), vin("Q", 0, 3)], "vout": [{"value": 4}]},
    "P":  {"vin": [vin("OP", 0, 1)], "vout": [{"value": 1}]},
    "Q":  {"vin": [vin("OQ", 0, 3)], "vout": [{"value": 3}]},
    "OP": {"vin": cb_vin(), "vout": [{"value": 1}]},
    "OQ": {"vin": cb_vin(), "vout": [{"value": 3}]},
}


def _ab_link(in_vals, out_vals):
    return [[0.5], [0.5]] if len(in_vals) == 2 else [[1.0]]


def test_multiplicity_does_not_move_the_bound():
    """The amount channel is refuse-only: it may cut a coin, never weight one.

    Same DAG twice; the only difference is W(E) on one branch. Under the contract the reported
    anonymity must be identical.
    """
    flat = path_count.path_count_anonymity(
        ("T", 0), depth=6, fetch=make_fetch(_AB_TXS), link_oracle=_ab_link,
        count_oracle=lambda i, o: count_report(0.0))
    skew = path_count.path_count_anonymity(
        ("T", 0), depth=6, fetch=make_fetch(_AB_TXS), link_oracle=_ab_link,
        count_oracle=lambda i, o: count_report(math.log(10.0) if i == [1] else 0.0))

    assert flat["min_entropy"] == pytest.approx(skew["min_entropy"])
    assert flat["shannon"] == pytest.approx(skew["shannon"])
    assert flat["origins_weighted"] == pytest.approx(skew["origins_weighted"])


def test_the_dead_mass_key_is_gone():
    res = path_count.path_count_anonymity(
        ("T", 0), depth=6, fetch=make_fetch(_AB_TXS), link_oracle=_ab_link,
        count_oracle=lambda i, o: count_report(0.0))
    assert "log_W_paths" not in res
    assert set(res) == {"origins_weighted", "min_entropy", "shannon", "truncated"}


def test_the_results_doc_states_the_contract_and_its_cost():
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    doc = open(os.path.join(root, "results", "RESULTS-path-count.md")).read()
    assert "refuse-only" in doc
    assert "no structural property" in doc


def test_no_document_says_the_walk_weights_by_multiplicity():
    """The claim, not three phrasings of it.

    An earlier guard pinned three literal strings in two files and declared rewording a review
    question rather than a test question. Four sites then restated the retracted claim in other
    words and stayed green, one of them the paper's own abstract. This sweeps every tracked
    document and module for a weighting applied to the subset-sum count under any of its names.

    Adjacency, not sentence scope: the abstract's restatement shared its sentence with "never a
    privacy score", so any sentence-level negation test cleared it. And the object is the subset-sum
    COUNT -- the subset-sum link matrix is the walk's correct and current weighting, so naming
    "subset-sum" alone would flag every honest site.
    """
    import os, re, glob
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    obj = r"(?:multiplicity|W\(E\)|subset-sum (?:path )?count)"
    claim = re.compile(r"weight(?:s|ed|ing)?\b[^.\n]{0,50}?\b" + obj, re.I)
    withdrawing = re.compile(r"\b(?:not|never|no longer|without|withdrawn|retired|removed|out of"
                             r"|earlier revisions?|once|gone|has left|nothing)\b", re.I)
    # superpowers/ records what was planned; counting.py's results doc is about the object that
    # legitimately counts multiplicity; this file must state the claim in order to ban it.
    exempt = re.compile(r"docs/superpowers/|\.venv/|results/RESULTS-counting-methods\.md"
                        r"|tests/test_path_count\.py")

    offenders = []
    for pattern in ("**/*.md", "**/*.py"):
        for path in glob.glob(os.path.join(root, pattern), recursive=True):
            rel = os.path.relpath(path, root)
            if exempt.search(rel):
                continue
            text = open(path, encoding="utf-8", errors="replace").read()
            for m in claim.finditer(text):
                if withdrawing.search(text[max(0, m.start() - 90):m.start()]):
                    continue
                offenders.append(f"{rel}: " + " ".join(text[m.start():m.end() + 20].split()))
    assert not offenders, "the retracted claim is restated in:\n" + "\n".join(offenders)
