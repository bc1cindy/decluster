"""Cluster-bits anchor (§1 '>100 bits') — pure, offline (synthetic slice)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def _tx(txid, ins, outs):
    return {"txid": txid,
            "vin": [{"prevout": {"scriptpubkey_address": a}} for a in ins],
            "vout": [{"scriptpubkey_address": a} for a in outs]}

def test_cluster_bits_sums_counterparty_rarity():
    from examples.cluster_bits import cluster_bits
    # tx1: A,B co-spend -> cluster {A,B}, both pay X;  tx2: A pays Y
    sample = [(_tx("t1", ["A", "B"], ["X"]), 1), (_tx("t2", ["A"], ["Y"]), 1)]
    rows = cluster_bits(sample)
    assert len(rows) == 1
    r = rows[0]
    assert r["members"] == 2 and r["counterparties"] == 2      # {A,B} touch {X,Y}
    # cbits: X touched by 2/4 nodes -> 1.0 bit; Y by 1/4 -> 2.0 bits; sum = 3.0
    assert abs(r["total_bits"] - 3.0) < 1e-9
    assert abs(r["topk_bits"] - 3.0) < 1e-9                    # <=5 counterparties -> floor == total

def test_summary_fractions_and_median():
    from examples.cluster_bits import summary
    rows = [{"total_bits": b, "topk_bits": min(b, 5.0)} for b in (1.0, 20.0, 120.0)]
    s = summary(rows)
    assert s["n_clusters"] == 3
    assert abs(s["median_total_bits"] - 20.0) < 1e-9
    assert abs(s["max_total_bits"] - 120.0) < 1e-9
    assert abs(s["frac>=1.6"] - 2 / 3) < 1e-9                  # 20 and 120 clear 1.6
    assert abs(s["frac>=100"] - 1 / 3) < 1e-9                  # only 120

def test_summary_empty():
    from examples.cluster_bits import summary
    assert summary([])["n_clusters"] == 0
    assert summary([{"total_bits": 0.0, "topk_bits": 0.0}])["n_clusters"] == 0   # 0-bit dropped

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
