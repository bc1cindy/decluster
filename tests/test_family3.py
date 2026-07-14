"""test change-relation extractors"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def _tx(vals, otypes=None, oaddr=None, itypes=None, iaddr=None):
    n = len(vals)
    otypes = otypes or ["v0_p2wpkh"]*n
    oaddr = oaddr or [f"o{i}" for i in range(n)]
    itypes = itypes or ["v0_p2wpkh"]
    iaddr = iaddr or ["i0"]
    return {"vin": [{"prevout": {"scriptpubkey_type": t, "scriptpubkey_address": a}}
                    for t, a in zip(itypes, iaddr)],
            "vout": [{"value": v, "scriptpubkey_type": t, "scriptpubkey_address": a}
                     for v, t, a in zip(vals, otypes, oaddr)]}

def test_change_index():
    from decluster.extractors import x_change_index
    # payment 100000 (round, 5 zeros) at idx0; change 43217 (arbitrary) at idx1 -> change is last
    assert x_change_index(_tx([100000, 43217])) == "last"
    assert x_change_index(_tx([43217, 100000])) == "first"
    assert x_change_index(_tx([100000, 100000])) == "na"   # tie -> ambiguous
    assert x_change_index(_tx([1, 2, 3])) == "na"           # not 2-out

def test_change_type_match():
    from decluster.extractors import x_change_type_match
    # change (idx1, arbitrary 43217) type matches the single input type
    assert x_change_type_match(_tx([100000, 43217], otypes=["v0_p2wpkh", "v0_p2wpkh"],
                                    itypes=["v0_p2wpkh"])) == "match_input"
    assert x_change_type_match(_tx([100000, 43217], otypes=["v0_p2wpkh", "v1_p2tr"],
                                    itypes=["v0_p2wpkh"])) == "mismatch_input"

def test_change_matches_output():
    from decluster.extractors import x_change_matches_output
    assert x_change_matches_output(_tx([100000, 43217], otypes=["v0_p2wpkh", "v0_p2wpkh"])) == "match_output"
    assert x_change_matches_output(_tx([100000, 43217], otypes=["v1_p2tr", "v0_p2wpkh"])) == "mismatch_output"

def test_change_address_reuse():
    from decluster.extractors import x_change_address_reuse
    assert x_change_address_reuse(_tx([100000, 43217], oaddr=["x", "i0"], iaddr=["i0"])) == "reuse"
    assert x_change_address_reuse(_tx([100000, 43217], oaddr=["x", "y"], iaddr=["i0"])) == "none"

if __name__ == "__main__":
    passed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print(f"  ok  {name}"); passed += 1
    print(f"{passed} passed")
