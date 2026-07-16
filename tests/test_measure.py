"""measure.load_ndjson coercion + load_unique dedup/keep."""
import sys, os, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def _write(rows):
    p = tempfile.mkstemp(suffix=".json")[1]
    with open(p, "w") as f: json.dump(rows, f)
    return p

def test_load_ndjson_reads_json_array():
    from decluster.measure import load_ndjson
    out = load_ndjson(_write([{"txid": "T1", "height": 100, "vin": [], "vout": []}]))
    assert len(out) == 1
    tx, h = out[0]
    assert tx["txid"] == "T1" and h == 100

def test_load_unique_dedups_by_txid():
    from decluster.measure import load_unique
    p1 = _write([{"txid": "T1", "vin": [], "vout": []}, {"txid": "T2", "vin": [], "vout": []}])
    p2 = _write([{"txid": "T2", "vin": [], "vout": []}, {"txid": "T3", "vin": [], "vout": []}])  # T2 dup
    assert [t["txid"] for t, _ in load_unique([p1, p2])] == ["T1", "T2", "T3"]

def test_load_unique_keep_filter():
    from decluster.measure import load_unique
    p = _write([{"txid": "T1", "vin": [], "vout": []}, {"txid": "T2", "vin": [], "vout": []}])
    kept = load_unique([p], keep=lambda tx: tx["txid"] != "T2")
    assert [t["txid"] for t, _ in kept] == ["T1"]

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
