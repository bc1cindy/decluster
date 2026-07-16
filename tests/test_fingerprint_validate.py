"""Canonical fingerprint-pair validation — pure, offline (synthetic txs, stub combiner)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def _tx(txid, addr):
    return {"txid": txid, "vin": [{"prevout": {"scriptpubkey_address": addr}}], "vout": []}

def _addrs(t):
    return {v.get("prevout", {}).get("scriptpubkey_address") for v in t["vin"]} - {None}

def test_reuse_pairs_positives_share_address():
    from decluster.fingerprint_validate import reuse_pairs
    txs = [_tx("T1", "A"), _tx("T2", "A"), _tx("T3", "B"), _tx("T4", "C")]   # only T1,T2 share
    pos, neg = reuse_pairs(txs, cap=50, seed=0)
    assert pos and all(_addrs(a) & _addrs(b) for a, b in pos)                # every positive shares
    assert all({a["txid"], b["txid"]} == {"T1", "T2"} for a, b in pos)       # the one real reuse group
    assert all(a["txid"] != b["txid"] for a, b in neg)                       # negatives are distinct txs

def test_reuse_pairs_no_sharing_yields_no_positives():
    from decluster.fingerprint_validate import reuse_pairs
    txs = [_tx("T1", "A"), _tx("T2", "B"), _tx("T3", "C")]                   # all distinct addresses
    pos, _ = reuse_pairs(txs, cap=50, seed=0)
    assert pos == []

def test_evaluate_separates_with_stub_combiner():
    from decluster.fingerprint_validate import evaluate
    txs = [_tx("A1", "A"), _tx("A2", "A"), _tx("B1", "B"), _tx("C1", "C"),
           _tx("D1", "D"), _tx("E1", "E"), _tx("F1", "F"), _tx("G1", "G")]   # only A1,A2 share
    class Stub:
        def score(self, a, b):
            return 10.0 if _addrs(a) & _addrs(b) else -10.0
    r = evaluate(txs, Stub(), cap=50, seed=0)
    assert r["auc"] is not None and r["auc"] > 0.85       # positives (shared) rank above negatives
    assert 0.3 < r["shuffle_auc"] < 0.7                   # shuffle control ~0.5
    assert r["n_pos"] > 0 and r["n_neg"] > 0

def test_load_blkcache_reads_dir(tmpdir=None):
    import json, tempfile, os as _os
    from decluster.fingerprint_validate import load_blkcache
    d = tempfile.mkdtemp()
    json.dump([{"txid": "T1", "vin": [{"prevout": {}}], "vout": []},
               {"txid": "T1", "vin": [{"prevout": {}}], "vout": []},   # dup txid -> deduped
               {"no_vin": True}],                                       # skipped (no vin)
              open(_os.path.join(d, "page0.json"), "w"))
    txs = load_blkcache(d)
    assert [t["txid"] for t in txs] == ["T1"]

def test_library_scorer_covers_full_library():
    from decluster.fingerprint_validate import LibraryScorer
    names = {a[0] for a in LibraryScorer().axes}
    assert len(names) >= 15                          # full library, NOT the 3-axis combiner
    assert {"low_r", "uih", "sighash"} <= names      # witness/uih axes ARE in the scored path

def test_library_scorer_identical_tx_is_positive():
    from decluster.fingerprint_validate import LibraryScorer
    tx = {"version": 2, "locktime": 0, "fee": 300, "weight": 800,
          "vin": [{"txid": "aa" * 32, "vout": 0, "sequence": 0xfffffffd,
                   "prevout": {"value": 3000, "scriptpubkey_type": "v0_p2wpkh", "scriptpubkey_address": "bc1qa"},
                   "witness": ["30450221" + "11" * 33, "02" + "11" * 32]},
                  {"txid": "bb" * 32, "vout": 1, "sequence": 0xfffffffd,
                   "prevout": {"value": 4000, "scriptpubkey_type": "v0_p2wpkh", "scriptpubkey_address": "bc1qb"},
                   "witness": ["30450221" + "11" * 33, "02" + "11" * 32]}],
          "vout": [{"value": 900, "scriptpubkey_type": "v0_p2wpkh", "scriptpubkey_address": "bc1qc"},
                   {"value": 6000, "scriptpubkey_type": "v0_p2wpkh", "scriptpubkey_address": "bc1qd"}]}
    assert LibraryScorer().score(tx, tx) > 0          # identical txs -> agreements only -> positive bits

def test_reuse_pairs_tolerates_prevout_none():
    from decluster.fingerprint_validate import reuse_pairs
    # a coinbase-style input carries prevout=None; reuse_pairs must not crash on it
    txs = [{"txid": "CB", "vin": [{"prevout": None, "is_coinbase": True}], "vout": []},
           {"txid": "T1", "vin": [{"prevout": {"scriptpubkey_address": "A"}}], "vout": []},
           {"txid": "T2", "vin": [{"prevout": {"scriptpubkey_address": "A"}}], "vout": []}]
    pos, neg = reuse_pairs(txs, cap=10, seed=0)
    assert all({a["txid"], b["txid"]} == {"T1", "T2"} for a, b in pos)   # only the real reuse group

def test_load_blkcache_skips_coinbase_and_uncached():
    import json, tempfile, os as _os
    from decluster.fingerprint_validate import load_blkcache
    d = tempfile.mkdtemp()
    json.dump([{"txid": "CB", "vin": [{"is_coinbase": True, "prevout": None}], "vout": []},
               {"txid": "T1", "vin": [{"prevout": {"scriptpubkey_address": "A"}}], "vout": []}],
              open(_os.path.join(d, "p.json"), "w"))
    assert [t["txid"] for t in load_blkcache(d)] == ["T1"]   # coinbase dropped

def test_library_scorer_locktime_not_inert():
    from decluster.fingerprint_validate import LibraryScorer
    lp = dict((a[0], a[2]) for a in LibraryScorer().axes)["locktime"]
    # height_* sub-classes folded into the "height" bucket the extractor emits -> axis is not inert
    assert "height" in lp and "zero" in lp and "timestamp" in lp

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
