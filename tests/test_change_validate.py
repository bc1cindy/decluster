"""Validation metrics: per-axis M&N-style TPR/FPR, combined pre<->post AUC, shuffle null control.
All offline on synthetic dicts + a stub combiner."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.change_validate import axis_vote, per_axis_rates, combined_auc

def _tx(txid, order_vals, seq=0xFFFFFFFD):
    """2-output tx; output values control x_output_order (sorted vs unsorted)."""
    return {"txid": txid, "locktime": 0, "version": 2,
            "vin": [{"txid": "f", "vout": 0, "sequence": seq, "prevout": {"value": 9}}],
            "vout": [{"value": v, "scriptpubkey_type": "v0_p2wpkh", "scriptpubkey_address": "a"}
                     for v in order_vals]}

def _fetchers(txs, spends):
    return (lambda t: txs[t]), (lambda t: spends[t])

def _axis_const(val):
    return lambda tx: val

def test_axis_vote_single_match():
    T = _tx("T", [1, 2]); S0 = _tx("S0", [1, 2]); S1 = _tx("S1", [1, 2])
    txs = {"T": T, "S0": S0, "S1": S1}
    spends = {"T": [{"spent": True, "txid": "S0"}, {"spent": True, "txid": "S1"}]}
    gt, os_ = _fetchers(txs, spends)
    # axis value: T="x"; S0="x" (match), S1="y" (no match) -> vote 0
    calls = {"T": "x", "S0": "x", "S1": "y"}
    fn = lambda tx: calls[tx["txid"]]
    assert axis_vote(T, fn, gt, os_) == 0

def test_axis_vote_none_when_both_match():
    T = _tx("T", [1, 2]); S0 = _tx("S0", [1, 2]); S1 = _tx("S1", [1, 2])
    txs = {"T": T, "S0": S0, "S1": S1}
    spends = {"T": [{"spent": True, "txid": "S0"}, {"spent": True, "txid": "S1"}]}
    gt, os_ = _fetchers(txs, spends)
    assert axis_vote(T, _axis_const("x"), gt, os_) is None     # both match -> ambiguous

def test_axis_vote_none_when_unspent():
    T = _tx("T", [1, 2])
    txs = {"T": T}
    spends = {"T": [{"spent": False, "txid": None}, {"spent": False, "txid": None}]}
    gt, os_ = _fetchers(txs, spends)
    assert axis_vote(T, _axis_const("x"), gt, os_) is None

def test_per_axis_rates():
    # one GT tx, change_index=0; axis votes correctly -> tpr=1, fpr=0, coverage=1
    T = _tx("T", [1, 2]); S0 = _tx("S0", [1, 2]); S1 = _tx("S1", [2, 1])
    txs = {"T": T, "S0": S0, "S1": S1}
    spends = {"T": [{"spent": True, "txid": "S0"}, {"spent": True, "txid": "S1"}]}
    gt, os_ = _fetchers(txs, spends)
    records = [{"tx": T, "change_index": 0}]
    rates = per_axis_rates(records, gt, os_)
    # output_order: T sorted[1,2]; S0 sorted (match), S1 unsorted (no match) -> vote 0 == label
    assert rates["output_order"] == (1.0, 0.0, 1.0)

def test_combined_auc_and_shuffle():
    from decluster.change_score import output_score  # noqa: ensure import path
    class StubCombiner:
        def __init__(self, table): self.table = table
        def score(self, a, b): return self.table[(a["txid"], b["txid"])]
    records, txs, spends, table = [], {}, {}, {}
    for k in range(12):
        tid, s0, s1 = f"T{k}", f"S{k}a", f"S{k}b"
        txs[tid] = _tx(tid, [1, 2]); txs[s0] = _tx(s0, [1, 2]); txs[s1] = _tx(s1, [1, 2])
        spends[tid] = [{"spent": True, "txid": s0}, {"spent": True, "txid": s1}]
        table[(tid, s0)] = 5.0; table[(tid, s1)] = -1.0     # change (idx 0) always agrees more
        records.append({"tx": txs[tid], "change_index": 0})
    gt, os_ = _fetchers(txs, spends)
    r = combined_auc(records, StubCombiner(table), gt, os_, seed=1)
    assert r["n_paired"] == 12
    assert r["auc"] == 1.0                     # change output always scores above spend
    assert r["shuffle_auc"] < 0.95             # randomizing the label breaks the signal

def test_universal_baseline_rates():
    from decluster.change_validate import universal_baseline_rates
    # output 0 less-round (12345) vs output 1 round (10000) -> change vote = 0 == label
    T = {"txid": "T", "vin": [{"prevout": {}}],
         "vout": [{"value": 12345}, {"value": 10000}]}
    assert universal_baseline_rates([{"tx": T, "change_index": 0}]) == (1.0, 0.0, 1.0)

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
