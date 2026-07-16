"""Layer 2 — generic engine: extractors + sample -> distribution and evidence bits."""
import math
from collections import Counter
from .fetch import recent_blocks, fetch_block_txs

def locktime_class(tx, block_height=None):
    lt = tx["locktime"]
    if lt == 0: return "zero"
    if lt >= 500_000_000: return "timestamp"
    if block_height is None: return "height"
    d = block_height - lt
    if -1 <= d <= 1: return "height_tip"
    if 1 < d <= 100: return "height_backdated"
    return "height_other"

def sample_recent_txs(n_blocks=15, slices_per_block=2):
    out = []
    for b in recent_blocks()[:n_blocks]:
        for s in range(slices_per_block):
            try: txs = fetch_block_txs(b["id"], s*25)
            except Exception: continue
            for tx in txs:
                if tx["vin"] and tx["vin"][0].get("is_coinbase"): continue
                out.append((tx, b["height"]))
    return out

def measure(sample, extractors):
    dist = {n: Counter() for n in extractors}
    for tx, h in sample:
        for n, fn in extractors.items():
            try: v = fn(tx, h) if fn.__code__.co_argcount == 2 else fn(tx)
            except Exception: v = "ERR"
            dist[n][v] += 1
    rep = {}
    for n, c in dist.items():
        tot = sum(c.values()); H = 0.0; rows = []
        for val, k in c.most_common():
            p = k/tot; H += -p*math.log2(p)
            rows.append((val, k, p, -math.log2(p)))
        rep[n] = {"total": tot, "entropy_bits": H, "rows": rows}
    return rep

def print_report(rep):
    for n, r in rep.items():
        print(f"\n== {n}  (n={r['total']}, entropy={r['entropy_bits']:.2f} bits) ==")
        for val, k, p, bits in r["rows"]:
            print(f"  {val:16} {k:>5} {p*100:>6.2f}% {bits:>7.2f} bits/match")
