"""Audit fixes: x_uih reads prevout.value; combiner mismatch weight never turns positive."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_uih_reads_prevout_value():
    from decluster.extractors import x_uih
    # prevout-only shape: input value ONLY under prevout.value (no top-level vin.value)
    tx = {"vin": [{"prevout": {"value": 1000}}, {"prevout": {"value": 50}}],
          "vout": [{"value": 900}, {"value": 100}]}
    assert x_uih(tx) == "uih1"          # max input 1000 >= max output 900

def test_uih_bigquery_shape_still_works():
    from decluster.extractors import x_uih
    tx = {"vin": [{"value": 1000, "prevout": {"value": 1000}}, {"value": 50, "prevout": {"value": 50}}],
          "vout": [{"value": 900}, {"value": 100}]}
    assert x_uih(tx) == "uih1"

def test_fs_score_mismatch_clamped():
    from decluster.combiner import fs_score
    # one degenerate axis: collision (0.999) >= consistency (0.95) -> a mismatch must clamp to <= 0
    axes = [("probe", lambda tx: tx["probe"], {"a": 1.0, "b": 1.0}, 0.999, lambda va, vb: False)]
    total = fs_score(axes, {"probe": "a"}, {"probe": "b"}, c=0.95, floor_n=1000)
    assert total <= 0        # without the clamp this would be +5.6 bits (a false same-owner vote)

def test_extractors_tolerate_prevout_none():
    from decluster import extractors as ex
    # a coinbase / uncached input carries prevout=None; the prevout-reading extractors must not crash
    cb = {"locktime": 0, "version": 2, "vin": [{"prevout": None, "is_coinbase": True}],
          "vout": [{"value": 100}]}
    for fn in (ex.x_uih, ex.x_input_script_type, ex.x_input_types_present, ex.x_multisig,
               ex.x_nested_segwit, ex.x_pubkey_compression, ex.x_change_address_reuse):
        fn(cb)                       # must not raise
    assert ex.x_uih(cb) == "none"

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
