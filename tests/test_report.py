import pytest
from decluster import report


def cb_vin():
    return [{"is_coinbase": True, "prevout": None}]


def vin(txid, vout, value):
    return {"is_coinbase": False, "txid": txid, "vout": vout, "prevout": {"value": value}}


def test_report_computes_amount_and_targets_without_pair():
    txs = {
        "C": {"txid": "C", "vin": [vin("P", 0, 5)],
              "vout": [{"value": 5, "scriptpubkey_type": "v0_p2wpkh"}]},
        "P": {"vin": cb_vin(), "vout": [{"value": 5}]},
    }
    fake_oracle = lambda i, o: {"coins": [{"role": "o", "index": 0, "value": 5,
                                           "log_w": 0.0, "kappa_c": 0.9}]}
    rep = report.report(txs["C"], fetch=lambda t: txs[t],
                        oracle=fake_oracle, link_oracle=lambda i, o: [[1.0]])
    assert [c.index for c in rep["amount"]] == [0]          # refuse-only cut fired (log_w 0 <= 1.0)
    assert set(rep["targets"]) == {0}                       # one spendable output
    assert rep["targets"][0]["min_entropy"] == pytest.approx(0.0)
    assert rep["leak"] is None and rep["topology"] is None  # no pair/graph context -> not fabricated
    assert "min_entropy" in rep["footing"]


def test_report_skips_op_return_outputs():
    txs = {
        "C": {"txid": "C", "vin": [vin("P", 0, 5)],
              "vout": [{"value": 5, "scriptpubkey_type": "v0_p2wpkh"},
                       {"value": 5, "scriptpubkey_type": "op_return"}]},  # positive value: only the type guard excludes it
        "P": {"vin": cb_vin(), "vout": [{"value": 5}]},
    }
    rep = report.report(txs["C"], fetch=lambda t: txs[t],
                        oracle=lambda i, o: {"coins": []},
                        link_oracle=lambda i, o: [[1.0, 0.0]])
    assert set(rep["targets"]) == {0}      # op_return vout 1 skipped
    assert rep["amount"] == []             # empty coins -> no cuts


def test_report_pairwise_terms_when_context_given():
    txs = {"C": {"txid": "C", "vin": [vin("P", 0, 5)],
                 "vout": [{"value": 5, "scriptpubkey_type": "v0_p2wpkh"}]},
           "P": {"vin": cb_vin(), "vout": [{"value": 5}]}}

    class FakeCombiner:
        def score(self, a, b):
            return 7.0

    rep = report.report(txs["C"], fetch=lambda t: txs[t],
                        oracle=lambda i, o: {"coins": []}, link_oracle=lambda i, o: [[1.0]],
                        pair={"txid": "D"}, combiner=FakeCombiner(),
                        neigh={"A": {"x"}, "B": {"x"}}, entities=(["A"], ["B"]))
    assert rep["leak"] == 7.0
    assert rep["topology"] is not None     # shared rare counterparty "x" -> corroborates


def test_report_targets_arg_restricts_walk():
    txs = {"C": {"txid": "C", "vin": [vin("P", 0, 5)],
                 "vout": [{"value": 5, "scriptpubkey_type": "v0_p2wpkh"},
                          {"value": 3, "scriptpubkey_type": "v0_p2wpkh"}]},
           "P": {"vin": cb_vin(), "vout": [{"value": 5}]}}
    rep = report.report(txs["C"], fetch=lambda t: txs[t],
                        oracle=lambda i, o: {"coins": []}, link_oracle=lambda i, o: [[1.0, 0.0]],
                        targets=[0])
    assert set(rep["targets"]) == {0}      # only the requested vout walked


def _round(total_in, outs):
    """A round reduced to what conservation reads: the total consumed and the outputs."""
    return {"txid": "R", "fee": 1000, "weight": 4000,
            "vin": [{"txid": "P", "vout": 0, "prevout": {"value": total_in}}],
            "vout": [{"value": v, "scriptpubkey_type": "v0_p2wpkh"} for v in outs]}


def test_the_forced_term_is_absent_rather_than_assumed():
    """Conservation needs one participant's input, which the transaction alone
    does not give — so without it the term is None, like leak and topology."""
    tx = _round(100, [20, 20, 20])
    rep = report.report(tx, fetch=lambda t: tx, oracle=lambda i, o: {"coins": []},
                        link_oracle=lambda i, o: [[1.0, 0.0, 0.0]])
    assert rep["forced"] is None


def test_the_forced_term_reports_what_the_others_could_not_have_funded():
    """others hold 50, so they afford two of the three 20s; the third has no source."""
    tx = _round(90, [20, 20, 20])
    rep = report.report(tx, fetch=lambda t: tx, oracle=lambda i, o: {"coins": []},
                        link_oracle=lambda i, o: [[1.0, 0.0, 0.0]], known_input=40)
    assert rep["forced"] == [(20, 1, 3)]


def test_the_forced_term_is_empty_when_the_inequality_does_not_bite():
    """The common answer: a participant small relative to the round forces nothing."""
    tx = _round(100, [20, 20, 20])
    rep = report.report(tx, fetch=lambda t: tx, oracle=lambda i, o: {"coins": []},
                        link_oracle=lambda i, o: [[1.0, 0.0, 0.0]], known_input=10)
    assert rep["forced"] == []


def _subjective_fetch_factory():
    txs = {
        "t1": {"txid": "t1",
               "vin": [{"txid": "p0", "vout": 0, "prevout": {"value": 500, "scriptpubkey_address": "a"}},
                       {"txid": "p1", "vout": 0, "prevout": {"value": 500}}],
               "vout": [{"value": 600, "scriptpubkey_address": "z"},
                        {"value": 399, "scriptpubkey_address": "a"}]},   # out1 reuses input-0 addr
        "p0": {"txid": "p0", "vin": [{"is_coinbase": True}], "vout": [{"value": 500}]},
        "p1": {"txid": "p1", "vin": [{"is_coinbase": True}], "vout": [{"value": 500}]},
    }
    return lambda txid: txs[txid]


def _uniform_link_oracle(ins, outs):
    return [[1.0] * len(outs) for _ in ins]


def test_report_adds_fused_headline_and_is_conservative():
    fetch = _subjective_fetch_factory()
    tx = fetch("t1")
    rep = report.report(tx, oracle=lambda i, o: {"coins": []}, link_oracle=_uniform_link_oracle,
                        fetch=fetch, depth=2, targets=[1], subjective=True)   # target the change/reused vout
    t = rep["targets"][1]
    assert "min_entropy" in t and "fused_min_entropy" in t
    # subjective same-owner evidence never raises the cut bound
    assert t["fused_min_entropy"] <= t["min_entropy"] + 1e-9


def test_fused_headline_is_clamped_when_subjective_pin_favors_graph_minority():
    """Reproduces the widening bug: a same-owner pin (via address reuse) on the graph-MINORITY
    input boosts it enough that the raw fused distribution is more spread than graph-only — which
    would violate the 'never widen' claim. The fused headline must be clamped to graph-only."""
    txs = {
        "t1": {"txid": "t1",
               "vin": [{"txid": "p0", "vout": 0, "prevout": {"value": 500}},
                       {"txid": "p1", "vout": 0, "prevout": {"value": 500,
                                                              "scriptpubkey_address": "shared"}}],
               "vout": [{"value": 990, "scriptpubkey_address": "shared"}]},  # reuse pins input 1
        "p0": {"txid": "p0", "vin": [{"is_coinbase": True}], "vout": [{"value": 500}]},
        "p1": {"txid": "p1", "vin": [{"is_coinbase": True}], "vout": [{"value": 500}]},
    }
    fetch = lambda txid: txs[txid]

    def skewed_link_oracle(ins, outs):
        # graph heavily favors input 0 (0.99) over input 1 (0.01) — input 1 is the graph-minority.
        if len(ins) == 2 and len(outs) == 1:
            return [[0.99], [0.01]]
        return [[1.0] * len(outs) for _ in ins]

    rep = report.report(txs["t1"], oracle=lambda i, o: {"coins": []}, link_oracle=skewed_link_oracle,
                        fetch=fetch, depth=2, targets=[0], subjective=True)
    t = rep["targets"][0]
    assert t["min_entropy"] < 0.1                    # graph-only: near-certain it's input 0's origin
    assert t["fused_min_entropy"] <= t["min_entropy"] + 1e-9   # clamp holds despite the minority boost


def test_report_subjective_false_is_graph_only_backward_compatible():
    fetch = _subjective_fetch_factory()
    tx = fetch("t1")
    rep = report.report(tx, oracle=lambda i, o: {"coins": []}, link_oracle=_uniform_link_oracle,
                        fetch=fetch, depth=2, targets=[0], subjective=False)
    t = rep["targets"][0]
    assert "min_entropy" in t and "fused_min_entropy" not in t   # unchanged graph-only shape


def test_report_cluster_of_feeds_subjective_source():
    fetch = _subjective_fetch_factory()
    tx = fetch("t1")
    # cluster that links input-0 addr "a" with output-0 addr "z" (from _subjective_fetch_factory's t1)
    from decluster.anonymity_set import cluster_of_from_groups
    cof = cluster_of_from_groups([["a", "z"]])
    rep = report.report(tx, oracle=lambda i, o: {"coins": []}, link_oracle=_uniform_link_oracle,
                        fetch=fetch, depth=2, targets=[0], subjective=True, cluster_of=cof)
    t = rep["targets"][0]
    assert "fused_min_entropy" in t and t["fused_min_entropy"] <= t["min_entropy"] + 1e-9
