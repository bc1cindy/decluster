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
