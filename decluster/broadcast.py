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
