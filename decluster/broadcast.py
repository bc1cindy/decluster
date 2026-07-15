"""Broadcast-time estimation from feerate ordering (no mempool logs) + the
locktime-vs-broadcast fingerprint axis. Pure core; network lives in annotate_broadcast."""

def tx_feerate(tx):
    """sat/vB from fee and weight; None for coinbase / missing (skip)."""
    fee, w = tx.get("fee"), tx.get("weight")
    if not fee or not w:
        return None
    return fee / (w / 4)

def broadcast_window(tx_fr, prev_min, prev_time, incl_time):
    """(tight, lo, hi) or None. Miners fill blocks by feerate, so if block N-1's cheapest
    tx (prev_min) is below T's feerate, T was not in the mempool at N-1 -> broadcast in
    (prev_time, incl_time]. Otherwise T may have waited -> loose (upper bound only)."""
    if tx_fr is None:
        return None
    if prev_min is not None and prev_min < tx_fr:
        return (True, prev_time, incl_time)
    return (False, None, incl_time)

def locktime_vs_broadcast(locktime, incl_height, win):
    """Compare nLocktime to the estimated broadcast height (~ incl_height when the bound is
    tight). This de-confounds the plain locktime axis: a tx that set locktime at broadcast and
    then waited reads `matches`, not `backdated`. `win` = broadcast_window(...) or None."""
    if locktime == 0:
        return "no_locktime"
    if locktime >= 500_000_000:
        return "timestamp"
    if win is None or not win[0]:              # no bound / loose -> cannot compare a height
        return "na_loose"
    n = incl_height
    if locktime > n + 1:
        return "future"
    if locktime >= n - 100:                     # anti-fee-sniping (incl. Core's random back-off)
        return "matches"
    return "backdated"

def annotate_broadcast(sample, fetch_block_hash, fetch_block):
    """Annotate each confirmed tx with tx['_bc'] = {prev_min, prev_time, incl_time} by fetching
    block N-1's minimum feerate (extras.feeRange[0]). Caches per block height. Fetch failures /
    missing feeRange leave the tx unannotated (extractor -> 'na')."""
    cache = {}
    for tx in sample:
        st = tx.get("status") or {}
        n = st.get("block_height")
        if n is None or n < 1:
            continue
        if n not in cache:
            try:
                prev = fetch_block(fetch_block_hash(n - 1))
                fr = (prev.get("extras") or {}).get("feeRange")
                cache[n] = {"prev_min": fr[0] if fr else None, "prev_time": prev.get("timestamp")}
            except Exception:
                cache[n] = None
        c = cache[n]
        if c and c["prev_min"] is not None:
            tx["_bc"] = {"prev_min": c["prev_min"], "prev_time": c["prev_time"],
                         "incl_time": st.get("block_time")}
