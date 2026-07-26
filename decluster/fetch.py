import os, json, urllib.request, time
CACHE = os.path.join(os.path.dirname(__file__), "..", ".cache")
BLK   = os.path.join(os.path.dirname(__file__), "..", ".blkcache")
os.makedirs(CACHE, exist_ok=True); os.makedirs(BLK, exist_ok=True)
API = "https://mempool.space/api"

_LAST = [0.0]          # last request timestamp (min interval throttle)
_MIN_INTERVAL = 0.2    # seconds between requests (polite)
_MAX_TRIES = 6

def _sleep(s):
    time.sleep(s)

def _request(url):
    import urllib.error
    for attempt in range(_MAX_TRIES):
        wait = _MIN_INTERVAL - (time.time() - _LAST[0])
        if wait > 0: _sleep(wait)
        try:
            body = urllib.request.urlopen(url, timeout=30).read().decode()
            _LAST[0] = time.time()
            return body
        except urllib.error.HTTPError as e:
            _LAST[0] = time.time()
            if e.code in (429, 500, 502, 503, 504) and attempt < _MAX_TRIES - 1:
                _sleep(2 ** attempt)          # exponential backoff: 1,2,4,8,16s
                continue
            raise
        except urllib.error.URLError:
            if attempt < _MAX_TRIES - 1:
                _sleep(2 ** attempt); continue
            raise
    raise RuntimeError("unreachable")

def _get(url):
    return json.loads(_request(url))

def _get_text(url):
    return _request(url).strip()

def _cached_json(path, url):
    if os.path.exists(path): return json.load(open(path))
    d = _get(url)
    json.dump(d, open(path, "w")); return d

def _cached_text(path, url):
    if os.path.exists(path): return open(path).read().strip()
    d = _get_text(url)
    open(path, "w").write(d); return d

def fetch_tx(txid):
    return _cached_json(os.path.join(CACHE, txid + ".json"), f"{API}/tx/{txid}")

def fetch_outspends(txid):
    """mempool.space /tx/:txid/outspends -> one entry per output:
    {"spent": bool, "txid": str|None, "vin": int|None, ...}. Cached like fetch_tx."""
    return _cached_json(os.path.join(CACHE, txid + ".outspends.json"), f"{API}/tx/{txid}/outspends")

def fetch_block_txs(block_id, index):
    return _cached_json(os.path.join(BLK, f"{block_id}_{index}.json"), f"{API}/block/{block_id}/txs/{index}")

def recent_blocks():
    return _get(f"{API}/v1/blocks")

def fetch_block(block_id):
    return _cached_json(os.path.join(CACHE, f"b{block_id}.json"), f"{API}/block/{block_id}")

def fetch_block_at(height):
    """Fetch block summary at exact height via /v1/blocks/:height; includes extras.feeRange."""
    p = os.path.join(CACHE, f"bh{height}.json")
    if os.path.exists(p): return json.load(open(p))
    blocks = _get(f"{API}/v1/blocks/{height}")
    # v1/blocks/:height returns up to 15 blocks ending at height; find the exact one
    d = next((b for b in blocks if b["height"] == height), blocks[0] if blocks else {})
    json.dump(d, open(p, "w")); return d

def fetch_tip_height():
    return _get(f"{API}/blocks/tip/height")

def fetch_block_hash(height):
    return _cached_text(os.path.join(CACHE, f"h{height}.txt"), f"{API}/block-height/{height}")
