"""fetch_outspends parses the mempool.space /tx/:txid/outspends array and caches it."""
import sys, os, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster import fetch

def test_parses_and_caches():
    tmp = tempfile.mkdtemp()
    fetch.CACHE = tmp
    canned = '[{"spent": true, "txid": "aa", "vin": 0}, {"spent": false, "txid": null, "vin": null}]'
    fetch._request = lambda url: canned
    r = fetch.fetch_outspends("deadbeef")
    assert r[0]["spent"] is True and r[0]["txid"] == "aa"
    assert r[1]["spent"] is False and r[1]["txid"] is None
    assert os.path.exists(os.path.join(tmp, "deadbeef.outspends.json"))
    # second call hits cache: break _request, still returns the same data
    fetch._request = lambda url: (_ for _ in ()).throw(AssertionError("should be cached"))
    assert fetch.fetch_outspends("deadbeef")[0]["txid"] == "aa"

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
