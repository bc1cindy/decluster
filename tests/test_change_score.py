"""Tx-level pre<->post score: output_score(T, i) = combiner bits between T and output i's spender;
None if that output is unspent. This compares T to its spender (disjoint from the co-spend label)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.change_score import spending_tx, output_score

def _tx(txid, seq=0xFFFFFFFD, lt=0):
    return {"txid": txid, "locktime": lt, "version": 2,
            "vin": [{"txid": "f", "vout": 0, "sequence": seq,
                     "prevout": {"value": 100000, "scriptpubkey_type": "v0_p2wpkh"}}],
            "vout": [{"value": 50000, "scriptpubkey_type": "v0_p2wpkh", "scriptpubkey_address": "a"}]}

class StubCombiner:
    def __init__(self, table): self.table = table
    def score(self, a, b): return self.table[(a["txid"], b["txid"])]

def _fetchers(txs, spends):
    return (lambda t: txs[t]), (lambda t: spends[t])

def test_spending_tx_none_when_unspent():
    T = _tx("T")
    spends = {"T": [{"spent": False, "txid": None}, {"spent": True, "txid": "S1"}]}
    gt, os_ = _fetchers({"T": T, "S1": _tx("S1")}, spends)
    assert spending_tx(T, 0, gt, os_) is None
    assert spending_tx(T, 1, gt, os_)["txid"] == "S1"

def test_output_score_is_combiner_bits_of_T_and_spender():
    T = _tx("T"); S0 = _tx("S0"); S1 = _tx("S1")
    spends = {"T": [{"spent": True, "txid": "S0"}, {"spent": True, "txid": "S1"}]}
    gt, os_ = _fetchers({"T": T, "S0": S0, "S1": S1}, spends)
    cmb = StubCombiner({("T", "S0"): 5.0, ("T", "S1"): -1.0})
    assert output_score(T, 0, cmb, gt, os_) == 5.0        # T vs its output-0 spender
    assert output_score(T, 1, cmb, gt, os_) == -1.0

def test_output_score_none_when_output_unspent():
    T = _tx("T")
    spends = {"T": [{"spent": True, "txid": "S0"}, {"spent": False, "txid": None}]}
    gt, os_ = _fetchers({"T": T, "S0": _tx("S0")}, spends)
    cmb = StubCombiner({("T", "S0"): 3.0})
    assert output_score(T, 0, cmb, gt, os_) == 3.0
    assert output_score(T, 1, cmb, gt, os_) is None

def test_integration_real_combiner_returns_float():
    from decluster.combiner import Combiner   # from .library import — a module, hermetic
    cmb = Combiner.from_library()
    T = _tx("T"); S0 = _tx("S0")               # identical construction -> some FS agreement
    spends = {"T": [{"spent": True, "txid": "S0"}, {"spent": False, "txid": None}]}
    gt, os_ = _fetchers({"T": T, "S0": S0}, spends)
    assert isinstance(output_score(T, 0, cmb, gt, os_), float)
    assert output_score(T, 1, cmb, gt, os_) is None

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
