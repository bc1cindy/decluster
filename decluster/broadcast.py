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
    tight). De-confounds the plain locktime axis, which compares locktime to the *inclusion*
    height: a tx that waited in the mempool looks heavily backdated there even if it set
    locktime at broadcast. Here a loose bound -> `na_loose` (abstain), refusing that misleading
    verdict; we judge matches/backdated/future only when broadcast is tightly bounded.
    `win` = broadcast_window(...) or None."""
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

def annotate_broadcast(sample, fetch_block_hash, fetch_block, fetch_block_at=None):
    """Annotate each confirmed tx with tx['_bc'] = {prev_min, prev_time, incl_time} by fetching
    block N-1's minimum feerate (extras.feeRange[0]). Caches per block height. Fetch failures /
    missing feeRange leave the tx unannotated (extractor -> 'na').
    fetch_block_at(height) -> block dict with extras; used when fetch_block lacks feeRange."""
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
                if fr is None and fetch_block_at is not None:
                    prev2 = fetch_block_at(n - 1)
                    fr = (prev2.get("extras") or {}).get("feeRange")
                    if prev2.get("timestamp"):
                        prev["timestamp"] = prev2["timestamp"]
                cache[n] = {"prev_min": fr[0] if fr else None, "prev_time": prev.get("timestamp")}
            except Exception:
                cache[n] = None
        c = cache[n]
        if c and c["prev_min"] is not None:
            tx["_bc"] = {"prev_min": c["prev_min"], "prev_time": c["prev_time"],
                         "incl_time": st.get("block_time")}

# --- cluster temporal fingerprint: when is a cluster active (hour-of-day / timezone) ---
import datetime

def tx_time(tx):
    """Best unix-time estimate of when a tx was broadcast: the tight-window midpoint when the
    feerate bound is tight, else the inclusion time (a coarser ~10-min-late proxy), else None."""
    bc = tx.get("_bc")
    if bc:
        win = broadcast_window(tx_feerate(tx), bc["prev_min"], bc["prev_time"], bc["incl_time"])
        if win and win[0]:
            return (win[1] + win[2]) / 2
    st = tx.get("status") or {}
    return st.get("block_time")

def active_hours(times):
    """24-bin UTC hour-of-day histogram of a cluster's tx times — its activity schedule."""
    hist = [0] * 24
    for t in times:
        if t is not None:
            hist[datetime.datetime.fromtimestamp(t, datetime.timezone.utc).hour] += 1
    return hist

def schedule_distance(a, b):
    """total-variation distance between two activity schedules (normalized hour histograms):
    0 = identical hours, 1 = disjoint. A temporal quasi-identifier for separating clusters."""
    sa, sb = sum(a), sum(b)
    if not sa or not sb:
        return 0.0
    return 0.5 * sum(abs(a[h] / sa - b[h] / sb) for h in range(24))

def calibrate_temporal(rows, min_txs=8, seed=0):
    """Validate the cluster temporal fingerprint on (addr, times) rows (`bigquery/temporal.sql`).
    Same owner = reused address. Returns (n_addrs, baseline_auc, persistence_auc, matched_auc):
      baseline    random split-half — CONFOUNDED: the two halves are i.i.d. samples of one
                  pooled distribution, so this measures activity *concentration* (does the addr
                  touch a narrow band of hours), not a persistent, owner-identifying schedule.
      persistence time-ordered split — does the schedule hold across the window?
      matched     persistence with negatives matched on active-hours count — removes the
                  concentration confound. matched ~ 0.5 => the schedule does NOT identify owners.
    On real 30-day data baseline is ~0.92 but matched collapses to ~0.49 (chance): the hour-of-day
    schedule does not separate owners once concentration is controlled for."""
    import random
    from collections import defaultdict
    from .graph_deanon import auc as _auc
    big = [[int(t) for t in r["times"]]                    # BigQuery INT64 -> JSON strings
           for r in rows if len(r.get("times") or []) >= min_txs]
    if len(big) < 2:
        return (len(big), None, None, None)
    rng = random.Random(seed)
    def sd(a, b): return schedule_distance(active_hours(a), active_hours(b))
    base_pos = []
    for ts in big:
        t = ts[:]; rng.shuffle(t); h = len(t) // 2
        base_pos.append(sd(t[:h], t[h:]))
    per_pos = [sd(t[:len(t) // 2], t[len(t) // 2:]) for t in map(sorted, big)]   # time-ordered
    n_neg = min(3000, len(big) * len(big))
    neg = [sd(a, b) for a, b in (rng.sample(big, 2) for _ in range(n_neg))]
    buckets = defaultdict(list)                            # by active-hours count
    for ts in big:
        buckets[sum(1 for c in active_hours(ts) if c)].append(ts)
    pickable = [k for k, v in buckets.items() if len(v) >= 2]
    mneg = [sd(*rng.sample(buckets[rng.choice(pickable)], 2)) for _ in range(n_neg)]
    A = lambda pos, ng: _auc([-x for x in pos], [-x for x in ng], seed)  # lower dist = more same
    return (len(big), A(base_pos, neg), A(per_pos, neg), A(per_pos, mneg))

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "temporal":
        # cluster temporal fingerprint calibration from a bigquery/temporal.sql export
        import json
        raw = open(sys.argv[2]).read().strip()
        rows = json.loads(raw) if raw.startswith("[") else [json.loads(l) for l in raw.splitlines() if l.strip()]
        n, base, per, matched = calibrate_temporal(rows)
        print(f"# temporal calibration: {n} reused addresses (>= 8 txs)")
        if base is None:
            print("insufficient data")
        else:
            print(f"baseline    random split-half AUC:  {base:.3f}  (confounded: concentration, not persistence)")
            print(f"persistence time-ordered split AUC: {per:.3f}")
            print(f"matched     band-width-matched AUC: {matched:.3f}  (~0.5 => schedule does NOT identify owner)")
    else:
        # calibrate the axis on a recent mempool.space sample: coverage (tight vs loose) + bits
        from .sampling import sample_chain_uniform
        from .fetch import fetch_block, fetch_block_hash, fetch_block_at
        from .engine import measure, print_report
        from .extractors import x_locktime_vs_broadcast
        sample = sample_chain_uniform(n_blocks=40, per_block=20, seed=0)
        annotate_broadcast((tx for tx, _ in sample), fetch_block_hash, fetch_block, fetch_block_at)
        tight = sum(1 for tx, _ in sample
                    if (w := broadcast_window(tx_feerate(tx),
                            (tx.get("_bc") or {}).get("prev_min"),
                            (tx.get("_bc") or {}).get("prev_time"),
                            (tx.get("_bc") or {}).get("incl_time"))) and w[0])
        n = len(sample)
        print(f"# {n} txs   tight coverage: {tight}/{n} = {100*tight/n:.1f}%")
        print_report(measure(sample, {"locktime_vs_broadcast": lambda t: x_locktime_vs_broadcast(t)}))
