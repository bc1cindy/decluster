import math
import pytest
from decluster import ancestry


def make_fetch(txs):
    return lambda txid: txs[txid]


def cb_vin():
    return [{"is_coinbase": True, "prevout": None}]


def vin(txid, vout, value):
    return {"is_coinbase": False, "txid": txid, "vout": vout, "prevout": {"value": value}}


def test_deterministic_provenance_is_zero_entropy():
    txs = {"C": {"vin": [vin("P", 0, 5)], "vout": [{"value": 5}]},
           "P": {"vin": cb_vin(), "vout": [{"value": 5}]}}
    out = ancestry.ancestry_entropy(("C", 0), fetch=make_fetch(txs), link_oracle=lambda i, o: [[1.0]])
    assert out["shannon"] == pytest.approx(0.0)
    assert out["min_entropy"] == pytest.approx(0.0)
    assert out["n_absorbers"] == 1
    assert out["truncated"] == 0


def test_flat_link_is_one_bit():
    txs = {"C": {"vin": [vin("P", 0, 5), vin("R", 0, 5)], "vout": [{"value": 10}]},
           "P": {"vin": cb_vin(), "vout": [{"value": 5}]},
           "R": {"vin": cb_vin(), "vout": [{"value": 5}]}}
    out = ancestry.ancestry_entropy(("C", 0), fetch=make_fetch(txs),
                                    link_oracle=lambda i, o: [[0.5], [0.5]])
    assert out["shannon"] == pytest.approx(1.0)
    assert out["min_entropy"] == pytest.approx(1.0)
    assert out["n_absorbers"] == 2


def test_shannon_bounded_by_log2_absorbers():
    txs = {"C": {"vin": [vin("P", 0, 5), vin("R", 0, 5)], "vout": [{"value": 10}]},
           "P": {"vin": cb_vin(), "vout": [{"value": 5}]},
           "R": {"vin": cb_vin(), "vout": [{"value": 5}]}}
    out = ancestry.ancestry_entropy(("C", 0), fetch=make_fetch(txs),
                                    link_oracle=lambda i, o: [[0.7], [0.3]])
    assert out["min_entropy"] <= out["shannon"] + 1e-12
    assert out["shannon"] <= math.log2(out["n_absorbers"]) + 1e-12


def test_truncated_counted_in_output():
    txs = {"C": {"vin": [vin("P", 0, 7)], "vout": [{"value": 7}]},
           "P": {"vin": cb_vin(), "vout": [{"value": 7}]}}
    out = ancestry.ancestry_entropy(("C", 0), fetch=make_fetch(txs), link_oracle=lambda i, o: None)
    assert out["truncated"] == 1
    assert out["shannon"] == pytest.approx(0.0)  # target is its own absorber
