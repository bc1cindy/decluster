"""Special-case change labelers. label_optimal_change reads ONLY values (the anti-circularity
property, encoded as test_optimal_change_reads_only_values)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.change_special import label_optimal_change, label_address_reuse, build_gt_special

def _tx(txid="T", in_vals=(100, 200), out_vals=(50, 500), in_addrs=("A", "B"), out_addrs=("c", "d"),
        seq=0xFFFFFFFD, ver=2, lt=0):
    return {"txid": txid, "locktime": lt, "version": ver,
            "vin": [{"txid": "f", "vout": 0, "sequence": seq,
                     "prevout": {"value": v, "scriptpubkey_address": a}}
                    for v, a in zip(in_vals, in_addrs)],
            "vout": [{"value": v, "scriptpubkey_address": a} for v, a in zip(out_vals, out_addrs)]}

def test_optimal_change_basic():
    assert label_optimal_change(_tx(in_vals=(100, 200), out_vals=(50, 500))) == 0   # 50 < min(100)
    assert label_optimal_change(_tx(in_vals=(100, 200), out_vals=(500, 50))) == 1   # tracks value

def test_optimal_change_needs_two_inputs():
    assert label_optimal_change(_tx(in_vals=(100,), out_vals=(50, 500))) is None

def test_optimal_change_not_decisive():
    # both outputs below the smallest input -> can't single out the change
    assert label_optimal_change(_tx(in_vals=(1000, 2000), out_vals=(50, 60))) is None
    # neither output below the smallest input -> None
    assert label_optimal_change(_tx(in_vals=(100, 200), out_vals=(150, 500))) is None

def test_optimal_change_missing_values():
    tx = _tx(in_vals=(100, 200), out_vals=(50, 500)); del tx["vin"][0]["prevout"]["value"]
    del tx["vin"][1]["prevout"]["value"]
    assert label_optimal_change(tx) is None

def test_optimal_change_reads_only_values():
    base = label_optimal_change(_tx(in_vals=(100, 200), out_vals=(50, 500))) ; assert base == 0
    # rewrite ALL addresses -> label unchanged (disjoint from addresses / co-spend)
    assert label_optimal_change(_tx(in_addrs=("X", "Y"), out_addrs=("z", "w"),
                                    in_vals=(100, 200), out_vals=(50, 500))) == base
    # junk nSequence/version/locktime -> label unchanged (disjoint from those fingerprints)
    assert label_optimal_change(_tx(in_vals=(100, 200), out_vals=(50, 500),
                                    seq=0x01, ver=1, lt=800000)) == base
    # change a value so nothing is < min input -> label drops (value-sensitive)
    assert label_optimal_change(_tx(in_vals=(100, 200), out_vals=(150, 500))) is None

def test_address_reuse():
    assert label_address_reuse(_tx(in_addrs=("A", "B"), out_addrs=("A", "d"))) == 0   # output0 == input A
    assert label_address_reuse(_tx(in_addrs=("A", "B"), out_addrs=("c", "d"))) is None
    assert label_address_reuse(_tx(in_addrs=("A", "B"), out_addrs=("A", "B"))) is None  # both -> None

def test_build_gt_special():
    keep = _tx("K", in_vals=(100, 200), out_vals=(50, 500))     # optimal-change -> 0
    drop = _tx("D", in_vals=(100,), out_vals=(50, 500))         # 1 input -> None
    assert build_gt_special([keep, drop], label_optimal_change) == [{"tx": keep, "change_index": 0}]

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
