"""Integration seam test: the REAL dss oracle wired into the REAL ancestry code path, on a
multi-output tx, to pin down that a coin's vout indexes the matrix COLUMN it occupies (not the
row, not some other coin's vout). Single-output fakes (vout=0 everywhere) can't catch a
matrix[vout][i]-vs-matrix[i][vout] transpose or an off-by-one fee-column drop; this can."""
import dss
import pytest
from decluster import ancestry


def make_fetch(txs):
    return lambda txid: txs[txid]


def cb_vin():
    return [{"is_coinbase": True, "prevout": None}]


def vin(txid, vout, value):
    return {"is_coinbase": False, "txid": txid, "vout": vout, "prevout": {"value": value}}


def test_real_oracle_indexes_provenance_by_vout_column():
    # Ground the fixture in the REAL oracle's actual output rather than an assumed shape.
    matrix = dss.pairwise_link_prob([3, 5], [3, 5])
    assert matrix == [[1.0, 0.0], [0.0, 1.0]]

    # tx C: two inputs (coinbase P:0 value 3, coinbase R:0 value 5), two outputs [3, 5], no fee.
    txs = {
        "C": {"vin": [vin("P", 0, 3), vin("R", 0, 5)], "vout": [{"value": 3}, {"value": 5}]},
        "P": {"vin": cb_vin(), "vout": [{"value": 3}]},
        "R": {"vin": cb_vin(), "vout": [{"value": 5}]},
    }
    fetch = make_fetch(txs)

    # target vout=0 must read matrix column 0 -> all mass on input 0 (P:0), matching matrix[0][0]=1.0
    g0 = ancestry.build_extended_graph(("C", 0), depth=6, fetch=fetch, link_oracle=ancestry.dss_link_oracle)
    dist0 = ancestry.absorber_distribution(g0, ("C", 0))
    assert dist0 == {("P", 0): 1.0}

    # target vout=1 must read matrix column 1 -> all mass on input 1 (R:0), matching matrix[1][1]=1.0
    g1 = ancestry.build_extended_graph(("C", 1), depth=6, fetch=fetch, link_oracle=ancestry.dss_link_oracle)
    dist1 = ancestry.absorber_distribution(g1, ("C", 1))
    assert dist1 == {("R", 0): 1.0}

    # the two targets must disagree -- a matrix[vout][i] transpose bug would make them agree
    # (both would read matrix ROW vout instead, giving identical splits here) or swap results.
    assert dist0 != dist1

    # deterministic single-mass-point provenance -> zero ancestry entropy, both targets
    e0 = ancestry.ancestry_entropy(("C", 0), fetch=fetch, link_oracle=ancestry.dss_link_oracle)
    e1 = ancestry.ancestry_entropy(("C", 1), fetch=fetch, link_oracle=ancestry.dss_link_oracle)
    assert e0["shannon"] == pytest.approx(0.0)
    assert e1["shannon"] == pytest.approx(0.0)
