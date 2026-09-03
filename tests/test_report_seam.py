"""End-to-end coverage for report()'s default walk and its explicit dss extension.

The default test must stay runnable in a checkout WITHOUT the compiled `dss` extension — that the
default takes no dss at all is half of what it asserts — so it stubs the amount channel's
transaction-level count oracle (refusing there short-circuits `amount_cuts` before the per-coin
`dss_oracle` is ever called). The dss arm below guards with `importorskip` on its own."""
import pytest

from decluster import ancestry, report


def cb_vin():
    return [{"is_coinbase": True, "prevout": None}]


def vin(txid, vout, value):
    return {"is_coinbase": False, "txid": txid, "vout": vout, "prevout": {"value": value}}


def no_counts(inputs, outputs):
    """A refusing count oracle: the amount channel is not what these tests measure, and its default
    routes through `dss`."""
    return {}


def test_report_uses_value_flow_by_default():
    txs = {
        "C": {"txid": "C", "vin": [vin("P", 0, 3), vin("R", 0, 5)],
              "vout": [{"value": 3, "scriptpubkey_type": "v0_p2wpkh"},
                       {"value": 5, "scriptpubkey_type": "v0_p2wpkh"}]},
        "P": {"vin": cb_vin(), "vout": [{"value": 3}]},
        "R": {"vin": cb_vin(), "vout": [{"value": 5}]},
    }
    rep = report.report(txs["C"], fetch=lambda t: txs[t], subjective=False,
                        count_oracle=no_counts)
    for target in rep["targets"].values():
        assert target["shannon"] == pytest.approx(0.954434002924965)
        assert target["n_absorbers"] == 2


def test_report_accepts_dss_as_an_explicit_extension():
    dss = pytest.importorskip("dss")
    # tx C: inputs (coinbase P:0=3, coinbase R:0=5), outputs [3, 5], no fee.
    # real dss.pairwise_link_prob([3,5],[3,5]) == [[1,0],[0,1]] -> vout 0 <- P, vout 1 <- R.
    assert dss.pairwise_link_prob([3, 5], [3, 5]) == [[1.0, 0.0], [0.0, 1.0]]
    txs = {
        "C": {"txid": "C", "vin": [vin("P", 0, 3), vin("R", 0, 5)],
              "vout": [{"value": 3, "scriptpubkey_type": "v0_p2wpkh"},
                       {"value": 5, "scriptpubkey_type": "v0_p2wpkh"}]},
        "P": {"vin": cb_vin(), "vout": [{"value": 3}]},
        "R": {"vin": cb_vin(), "vout": [{"value": 5}]},
    }
    rep = report.report(
        txs["C"], fetch=lambda t: txs[t],
        link_oracle=ancestry.dss_link_oracle, subjective=False,
    )
    assert set(rep["targets"]) == {0, 1}
    for vout in (0, 1):
        t = rep["targets"][vout]
        assert t["shannon"] == pytest.approx(0.0)      # deterministic provenance
        assert t["min_entropy"] == pytest.approx(0.0)
        assert t["n_absorbers"] == 1                    # single origin, no duplicate absorbers
        assert t["truncated"] == 0                      # walked to a real coinbase origin
