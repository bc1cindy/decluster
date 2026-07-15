"""test mempool.space fetch helpers"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_fetch_tip_height():
    import decluster.fetch as f
    saved = f._get
    try:
        f._get = lambda url: 840123 if url.endswith("/blocks/tip/height") else None
        assert f.fetch_tip_height() == 840123
    finally:
        f._get = saved

def test_fetch_block_hash():
    import decluster.fetch as f
    saved = f._get_text
    try:
        seen = {}
        def fake(url): seen["url"] = url; return "0000000000000000000abc"
        f._get_text = fake
        # bypass on-disk cache to force the request path
        import os
        p = os.path.join(f.CACHE, "h840123.txt")
        if os.path.exists(p): os.remove(p)
        assert f.fetch_block_hash(840123) == "0000000000000000000abc"
        assert seen["url"].endswith("/block-height/840123")
    finally:
        f._get_text = saved

def test_sample_chain_uniform_seeded():
    import decluster.sampling as su
    saved = (su.fetch_tip_height, su.fetch_block_hash, su.fetch_block_txs, su.fetch_block)
    try:
        su.fetch_tip_height = lambda: 800_000
        su.fetch_block_hash = lambda h: f"hash{h}"
        su.fetch_block = lambda block_id: {"tx_count": 1}
        su.fetch_block_txs = lambda block_id, off: [{
            "txid": f"{block_id}_{off}_a",
            "vin": [{"txid": "p", "vout": 0, "sequence": 0xFFFFFFFD, "is_coinbase": False}],
            "vout": [{"value": 1000, "scriptpubkey_type": "v0_p2wpkh"}],
            "version": 2, "locktime": 0}]
        a = su.sample_chain_uniform(n_blocks=5, per_block=1, seed=42)
        b = su.sample_chain_uniform(n_blocks=5, per_block=1, seed=42)
        assert [h for _, h in a] == [h for _, h in b]      # seeded => reproducible
        assert all(200_000 <= h <= 800_000 for _, h in a)  # within [floor, tip]
        assert len(a) == 5
    finally:
        su.fetch_tip_height, su.fetch_block_hash, su.fetch_block_txs, su.fetch_block = saved

def _tx(vout, vin=None, version=2):
    return {"version": version, "locktime": 0,
            "vin": vin or [{"txid": "p", "vout": 0, "sequence": 0xFFFFFFFD, "value": 5000}],
            "vout": vout}

def test_x_output_order():
    from decluster.extractors import x_output_order
    # sorted but small n -> coincidental (1/n!, n=2 is 1/2) -> small_n, not a confident tell
    assert x_output_order(_tx([{"value": 1, "scriptpubkey_type": "a"},
                               {"value": 2, "scriptpubkey_type": "b"}])) == "small_n"
    # sorted with n>=4 -> deliberate -> sorted_value
    assert x_output_order(_tx([{"value": i, "scriptpubkey_type": "a"} for i in (1, 2, 3, 4)])) == "sorted_value"
    assert x_output_order(_tx([{"value": 2, "scriptpubkey_type": "b"},
                               {"value": 1, "scriptpubkey_type": "a"}])) == "unsorted"
    assert x_output_order(_tx([{"value": 1, "scriptpubkey_type": "a"}])) == "single"

def test_x_change_spk_type():
    from decluster.extractors import x_change_spk_type
    assert x_change_spk_type(_tx([{"value": 1, "scriptpubkey_type": "v0_p2wpkh"},
                                  {"value": 2, "scriptpubkey_type": "v0_p2wpkh"}])) == "uniform_v0_p2wpkh"
    assert x_change_spk_type(_tx([{"value": 1, "scriptpubkey_type": "v0_p2wpkh"},
                                  {"value": 2, "scriptpubkey_type": "v1_p2tr"}])) == "mixed"

def test_x_version():
    from decluster.extractors import x_version
    assert x_version(_tx([{"value": 1, "scriptpubkey_type": "a"}], version=2)) == "v2"
    assert x_version(_tx([{"value": 1, "scriptpubkey_type": "a"}], version=1)) == "v1"

def test_x_uih():
    from decluster.extractors import x_uih
    assert x_uih(_tx([{"value": 100, "scriptpubkey_type": "a"}],
                     vin=[{"txid": "p", "vout": 0, "sequence": 1, "value": 4000},
                          {"txid": "q", "vout": 0, "sequence": 1, "value": 4000}])) == "uih1"
    assert x_uih(_tx([{"value": 5000, "scriptpubkey_type": "a"}],
                     vin=[{"txid": "p", "vout": 0, "sequence": 1, "value": 6000}])) == "none"

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print(f"  ok  {name}")
    print("7 passed")
