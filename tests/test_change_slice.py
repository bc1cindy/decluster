"""Slice adapter: build M&N same-owner change labels by multi-input cluster membership over a
contiguous slice, and expose slice fetchers matching change_score/change_validate. Offline tests."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.change_slice import index_slice, slice_fetchers, label_by_cluster, build_gt_slice

def _tx(txid, ins, outs, seq=0xFFFFFFFD, lt=0):
    """ins: list of (funding_txid, vout, addr). outs: list of addr (value auto)."""
    return {"txid": txid, "locktime": lt, "version": 2,
            "vin": [{"txid": ft, "vout": fv, "sequence": seq,
                     "prevout": {"value": 100000, "scriptpubkey_type": "v0_p2wpkh",
                                 "scriptpubkey_address": a}} for (ft, fv, a) in ins],
            "vout": [{"value": 50000 + i, "scriptpubkey_type": "v0_p2wpkh",
                      "scriptpubkey_address": a} for i, a in enumerate(outs)]}

def test_index_builds_txmap_spender_and_uf():
    # T spends coin (PF,0)@I1 -> outputs change C (idx0), payment P (idx1)
    # R later co-spends C with I1 -> unions C into I1's cluster (the reveal)
    T = _tx("T", [("PF", 0, "I1")], ["C", "P"])
    R = _tx("R", [("T", 0, "C"), ("W", 3, "I1")], ["X"])   # spends T output 0; co-spends C & I1
    Q = _tx("Q", [("T", 1, "P")], ["Y"])                   # spends T output 1
    by_txid, spender, uf = index_slice([T, R, Q])
    assert set(by_txid) == {"T", "R", "Q"}
    assert spender[("T", 0)] == "R" and spender[("T", 1)] == "Q"
    assert uf.find("C") == uf.find("I1")       # reveal: C clusters with the input
    assert uf.find("P") != uf.find("I1")       # payment does not

def test_slice_fetchers():
    T = _tx("T", [("PF", 0, "I1")], ["C", "P"])
    R = _tx("R", [("T", 0, "C"), ("W", 3, "I1")], ["X"])
    by_txid, spender, uf = index_slice([T, R])
    get_tx, get_outspends = slice_fetchers(by_txid, spender)
    assert get_tx("T")["txid"] == "T"
    os_ = get_outspends("T")
    assert os_[0] == {"spent": True, "txid": "R"}
    assert os_[1] == {"spent": False, "txid": None}        # P unspent in this slice

def test_label_output0_change():
    T = _tx("T", [("PF", 0, "I1")], ["C", "P"])
    R = _tx("R", [("T", 0, "C"), ("W", 3, "I1")], ["X"])
    _by, _sp, uf = index_slice([T, R])
    assert label_by_cluster(T, uf) == 0

def test_label_output1_change():
    # mirror: payment is idx0, change is idx1
    T = _tx("T", [("PF", 0, "I1")], ["P", "C"])
    R = _tx("R", [("T", 1, "C"), ("W", 3, "I1")], ["X"])
    _by, _sp, uf = index_slice([T, R])
    assert label_by_cluster(T, uf) == 1

def test_label_none_when_neither_clusters():
    T = _tx("T", [("PF", 0, "I1")], ["C", "P"])   # no later co-spend of C or P with I1
    _by, _sp, uf = index_slice([T])
    assert label_by_cluster(T, uf) is None

def test_label_none_when_both_cluster():
    T = _tx("T", [("PF", 0, "I1")], ["A", "B"])
    R = _tx("R", [("T", 0, "A"), ("W", 1, "I1")], ["X"])   # A clusters with I1
    S = _tx("S", [("T", 1, "B"), ("W", 2, "I1")], ["Y"])   # B also clusters with I1
    _by, _sp, uf = index_slice([T, R, S])
    assert label_by_cluster(T, uf) is None                 # two candidates -> drop

def test_label_none_when_change_reuses_input():
    T = _tx("T", [("PF", 0, "I1")], ["I1", "P"])           # output reuses the input address
    R = _tx("R", [("T", 0, "I1")], ["X"])
    _by, _sp, uf = index_slice([T, R])
    assert label_by_cluster(T, uf) is None                 # not fresh -> drop

def test_build_gt_slice_and_report_run():
    from decluster.change_validate import report
    T = _tx("T", [("PF", 0, "I1")], ["C", "P"])
    R = _tx("R", [("T", 0, "C"), ("W", 3, "I1")], ["X"])
    Q = _tx("Q", [("T", 1, "P")], ["Y"])
    by_txid, spender, uf = index_slice([T, R, Q])
    gt = build_gt_slice(by_txid, uf)
    assert gt == [{"tx": T, "change_index": 0}]
    get_tx, get_outspends = slice_fetchers(by_txid, spender)
    out = report(gt, get_tx=get_tx, get_outspends=get_outspends)   # smoke: runs end-to-end
    assert "GT change-id validation" in out and "input_order" in out

def _lean(txid, ins, outs, seq=0xFFFFFFFD, lt=0):
    """lean slice.sql schema: no scriptpubkey_type, no fee/weight, no nested input value."""
    return {"txid": txid, "locktime": lt, "version": 2,
            "vin": [{"txid": ft, "vout": fv, "sequence": seq,
                     "prevout": {"scriptpubkey_address": a}} for (ft, fv, a) in ins],
            "vout": [{"value": 50000 + i, "scriptpubkey_address": a} for i, a in enumerate(outs)]}

def test_mn_filter_reused_change_dropped():
    from decluster.change_slice import build_gt_slice_mn
    # T's change addr "C" is ALSO an output of an unrelated tx V -> reused -> dropped by filter A
    T = _tx("T", [("PF", 0, "I1")], ["C", "P"])
    R = _tx("R", [("T", 0, "C"), ("W", 3, "I1")], ["X"])
    V = _tx("V", [("PV", 0, "J1")], ["C", "Q"])           # "C" reused as an output here
    by, sp, uf = index_slice([T, R, V])
    gt, dropped = build_gt_slice_mn(by, uf)
    assert gt == [] and dropped["reused_change"] == 1

def test_mn_filter_fresh_change_kept():
    from decluster.change_slice import build_gt_slice_mn
    T = _tx("T", [("PF", 0, "I1")], ["C", "P"])
    R = _tx("R", [("T", 0, "C"), ("W", 3, "I1")], ["X"])  # C only appears as output in T
    Q = _tx("Q", [("T", 1, "P")], ["Y"])
    by, sp, uf = index_slice([T, R, Q])
    gt, dropped = build_gt_slice_mn(by, uf)
    assert gt == [{"tx": T, "change_index": 0}] and dropped["reused_change"] == 0

def test_mn_filter_twochange_cluster_excluded():
    from decluster.change_slice import build_gt_slice_mn
    # cluster I1 has 2 candidate txs; T2 has BOTH outputs in-cluster -> 50% > 10% -> whole cluster out
    T = _tx("T", [("PF", 0, "I1")], ["C", "P"])
    R = _tx("R", [("T", 0, "C"), ("W", 3, "I1")], ["X"])
    T2 = _tx("T2", [("PG", 0, "I1")], ["A", "B"])
    RA = _tx("RA", [("T2", 0, "A"), ("W", 4, "I1")], ["m"])   # A co-spent with I1
    RB = _tx("RB", [("T2", 1, "B"), ("W", 5, "I1")], ["k"])   # B co-spent with I1 -> T2 both-in
    by, sp, uf = index_slice([T, R, T2, RA, RB])
    gt, dropped = build_gt_slice_mn(by, uf)
    assert gt == [] and dropped["twochange_cluster"] >= 1

def test_lean_schema_end_to_end():
    from decluster.change_validate import report
    T = _lean("T", [("PF", 0, "I1")], ["C", "P"])
    R = _lean("R", [("T", 0, "C"), ("W", 3, "I1")], ["X"])
    Q = _lean("Q", [("T", 1, "P")], ["Y"])
    by_txid, spender, uf = index_slice([T, R, Q])
    gt = build_gt_slice(by_txid, uf)
    assert gt == [{"tx": T, "change_index": 0}]
    get_tx, get_outspends = slice_fetchers(by_txid, spender)
    out = report(gt, get_tx=get_tx, get_outspends=get_outspends)   # must not KeyError on missing type
    assert "input_order" in out and "combined pre<->post scorer" in out

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
