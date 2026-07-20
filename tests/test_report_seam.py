"""End-to-end: report() through the REAL dss oracle on a multi-output tx — verifies the orchestrator
reaches the compiled dss link matrix and populates one target per spendable output with a
deterministic-provenance lower bound. The column-vs-row (vout) indexing itself is discriminated by
tests/test_ancestry_seam.py, which asserts the resolved absorber identity on the same fixture; here
the matrix is the symmetric identity, so this test pins report()'s plumbing and the deterministic
outcome, not the transpose."""
import pytest

dss = pytest.importorskip("dss")
from decluster import report


def cb_vin():
    return [{"is_coinbase": True, "prevout": None}]


def vin(txid, vout, value):
    return {"is_coinbase": False, "txid": txid, "vout": vout, "prevout": {"value": value}}


def test_report_targets_through_real_dss_oracle():
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
    rep = report.report(txs["C"], fetch=lambda t: txs[t])   # real dss oracles (defaults)
    assert set(rep["targets"]) == {0, 1}
    for vout in (0, 1):
        t = rep["targets"][vout]
        assert t["shannon"] == pytest.approx(0.0)      # deterministic provenance
        assert t["min_entropy"] == pytest.approx(0.0)
        assert t["n_absorbers"] == 1                    # single origin, no duplicate absorbers
        assert t["truncated"] == 0                      # walked to a real coinbase origin
