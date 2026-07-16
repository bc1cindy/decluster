"""test witness-based fingerprint extractors"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def _w(*sigs):  # build a tx whose inputs carry the given witness[0] hex sigs
    return {"vin": [{"witness": [s, "02aa"]} if s else {"witness": []} for s in sigs],
            "vout": [{"value": 1, "scriptpubkey_type": "a"}]}

def test_x_low_r():
    from decluster.extractors import x_low_r
    assert x_low_r(_w("00"*71)) == "low_r"        # 71-byte DER incl sighash -> low-R
    assert x_low_r(_w("00"*72)) == "not_low_r"    # 72 -> padded r -> not low-R
    assert x_low_r(_w("00"*71, "00"*72)) == "not_low_r"  # any non-low -> not
    assert x_low_r(_w(None)) == "na"              # no witness sig

def test_x_sighash():
    from decluster.extractors import x_sighash
    assert x_sighash(_w("30" + "00"*69 + "01")) == "all"    # 71-byte ecdsa, sighash 0x01
    assert x_sighash(_w("30" + "00"*69 + "83")) == "anyonecanpay_single"
    assert x_sighash(_w("00"*64)) == "taproot_default"      # 64-byte schnorr
    assert x_sighash(_w("00"*65)) == "taproot_explicit"     # 65-byte schnorr
    assert x_sighash(_w(None)) == "na"

def test_library():
    from decluster.library import AXES, bits
    names = {a["axis"] for a in AXES}
    assert {"nsequence", "locktime", "low_r", "sighash"} <= names
    for a in AXES:
        assert a["extractor"] is not None
        assert "severity" in a and "bits" in a
    assert isinstance(bits("nsequence", "rbf_fffffffd"), float)
    assert isinstance(bits("low_r", "low_r"), float)
    assert bits("fee_rate", "anything") is None
    assert bits("nsequence", "no_such_value") is None

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print(f"  ok  {name}")
    print("2 passed")
