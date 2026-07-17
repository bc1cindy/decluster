"""Multi-era crawler + witness-bits-by-era — pure, offline (no network)."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_era_classifies_by_activation_height():
    from examples.era_crawler import era
    assert era(300000) == "pre-segwit"      # 2014
    assert era(481824) == "segwit"          # SegWit activation, inclusive
    assert era(600000) == "segwit"
    assert era(709632) == "taproot"         # Taproot activation, inclusive
    assert era(900000) == "taproot"

def test_targets_are_balanced_and_in_bounds():
    from examples.era_crawler import _targets, ERAS
    tip = 900000
    tg = _targets(8, tip)
    from collections import Counter
    per_era = Counter(name for name, _ in tg)
    assert per_era["pre-segwit"] == 8 and per_era["segwit"] == 8 and per_era["taproot"] == 8
    for name, h in tg:                       # every target inside its era's [lo, hi)
        lo, hi = next((lo, hi) for n, lo, hi in ERAS if n == name)
        assert lo <= h and (hi is None or h < hi)
        if name == "taproot":
            assert h < tip

def test_measure_bits_are_neg_log2_share_bucketed_by_era():
    from examples.witness_bits_by_era import measure
    # 4 taproot-era txs, all with empty witness -> every witness axis returns "na"
    txs = [{"status": {"block_height": 800000}, "vin": [{"witness": []}], "vout": [{}]}
           for _ in range(4)]
    out, sizes = measure(txs)
    assert sizes["taproot"] == 4 and sizes["segwit"] == 0
    na = out["low_r"]["taproot"]["na"]
    assert na[0] == 4 and abs(na[1] - 0.0) < 1e-9         # share 4/4 -> 0 bits
    assert "segwit" not in out["low_r"]                    # empty era omitted

def test_measure_partitions_share_within_era():
    from examples.witness_bits_by_era import measure
    # 1 nested-segwit tx + 3 plain, all taproot era -> nested share 1/4 -> 2 bits
    nested = {"status": {"block_height": 800000},
              "vin": [{"prevout": {"scriptpubkey_type": "p2sh"}, "witness": ["aa"]}], "vout": [{}]}
    plain = {"status": {"block_height": 800000}, "vin": [{"witness": []}], "vout": [{}]}
    out, _ = measure([nested] + [plain] * 3)
    ns = out["nested_segwit"]["taproot"]["nested_segwit"]
    assert ns[0] == 1 and abs(ns[1] - 2.0) < 1e-9          # -log2(1/4) = 2

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
