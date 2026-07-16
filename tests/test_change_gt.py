"""M&N change primitives: candidate detection and input/output addresses. (The change label itself
is cluster-membership, built and tested in change_slice.)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.change_gt import input_addrs, out_addr, is_candidate

def _tx(in_addrs, out_addrs):
    return {"vin": [{"prevout": {"scriptpubkey_address": a}} for a in in_addrs],
            "vout": [{"scriptpubkey_address": a, "value": 1000} for a in out_addrs]}

def test_is_candidate():
    assert is_candidate(_tx(["i1"], ["o0", "o1"]))
    assert not is_candidate(_tx(["i1"], ["o0", "o1", "o2"]))        # 3 outputs
    bad = _tx(["i1"], ["o0", "o1"]); bad["vout"][1]["scriptpubkey_address"] = None
    assert not is_candidate(bad)                                    # unspendable output

def test_input_addrs_skips_coinbase():
    t = _tx(["i1", "i2"], ["a", "b"])
    t["vin"].append({})                                            # coinbase-style input, no prevout
    assert input_addrs(t) == {"i1", "i2"}

def test_out_addr():
    t = _tx(["i1"], ["a", "b"])
    assert out_addr(t, 0) == "a" and out_addr(t, 1) == "b"

def test_union_input_addrs():
    from decluster.change_gt import union_input_addrs
    from decluster.unionfind import UF
    uf = UF()
    tx = {"vin": [{"prevout": {"scriptpubkey_address": "A"}},
                  {"prevout": {"scriptpubkey_address": "B"}},
                  {"prevout": None}]}            # None prevout skipped, no crash
    union_input_addrs(tx, uf)
    assert uf.find("A") == uf.find("B")

def test_input_addrs_tolerates_prevout_none():
    from decluster.change_gt import input_addrs
    assert input_addrs({"vin": [{"prevout": None}]}) == set()

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
