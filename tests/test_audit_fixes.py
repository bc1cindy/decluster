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

def test_combiner_mismatch_weight_clamped():
    import decluster.combiner as cm
    c = cm.Combiner.from_library()
    orig = cm.AXES
    cm.AXES = {"probe": lambda tx: tx["probe"]}          # single controlled axis
    try:
        c.freq["probe"] = {"a": 1.0, "b": 1.0}
        c.collision["probe"] = 0.999                     # degenerate: collision >= consistency (0.95)
        c.n = 2
        total = c.score({"probe": "a"}, {"probe": "b"})  # mismatch on probe
        assert total <= 0        # without the clamp this would be +5.6 bits (a false same-owner vote)
    finally:
        cm.AXES = orig

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
