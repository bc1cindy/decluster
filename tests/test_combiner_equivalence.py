"""Combiner.from_library().score must stay byte-identical across the fs_score refactor."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def _tx(seq, lt, txids):
    return {"locktime": lt, "vin": [{"sequence": seq, "txid": t, "vout": i} for i, t in enumerate(txids)]}

A = _tx(0xfffffffd, 0, ["aa" * 32, "bb" * 32])
B = _tx(0xffffffff, 800000, ["cc" * 32])
C = _tx(0xfffffffd, 0, ["aa" * 32, "bb" * 32])

def test_combiner_scores_unchanged():
    from decluster.combiner import Combiner
    c = Combiner.from_library()
    assert abs(c.score(A, C) - 2.7800000000000002) < 1e-9        # same-structure pair
    assert abs(c.score(A, B) - (-6.524772307464604)) < 1e-9      # different pair
    assert abs(c.score(B, B) - 2.763608937470405) < 1e-9         # identical single-input tx

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
