"""Unbiased sampling: spreads offsets across the whole block (not just the high-fee top).
Fixes the bias that gave locktime 83/17 instead of ~95/4.5."""
import random
from .fetch import recent_blocks, fetch_block_txs, fetch_tip_height, fetch_block_hash, fetch_block

def sample_spread(n_blocks=4, per_block=250):
    """~per_block txs spread uniformly across each of n_blocks recent blocks."""
    out = []
    for b in recent_blocks()[:n_blocks]:
        total = b.get("tx_count", 1)
        step = max(25, (total // per_block // 25) * 25 or 25)   # offsets in multiples of 25
        off = 0
        got = 0
        while off < total and got < per_block:
            try: txs = fetch_block_txs(b["id"], off)
            except Exception: break
            for tx in txs:
                if tx["vin"] and tx["vin"][0].get("is_coinbase"): continue
                out.append((tx, b["height"])); got += 1
            off += step
    return out

def sample_chain_uniform(n_blocks=40, per_block=8, seed=0, floor=200_000):
    """samples n_blocks uniform heights in [floor, tip]; per block, per_block txs from
    RANDOM offsets (spreads over fee: offset 0 = high-fee top). Fixes the intra-block bias."""
    rng = random.Random(seed)
    tip = fetch_tip_height()
    heights = sorted(rng.sample(range(floor, tip + 1), min(n_blocks, tip + 1 - floor)))
    out = []
    for h in heights:
        block_id = fetch_block_hash(h)
        try: total = fetch_block(block_id).get("tx_count", 1)
        except Exception: total = 1
        n_off = min(per_block, max(1, total // 25 + 1))
        offsets = sorted({(rng.randrange(0, total) // 25) * 25 for _ in range(n_off * 3)})[:n_off]
        for off in offsets:
            try: txs = fetch_block_txs(block_id, off)
            except Exception: continue
            for tx in txs:
                if tx["vin"] and tx["vin"][0].get("is_coinbase"): continue
                out.append((tx, h)); break   # 1 tx per offset -> spread over fee
    return out
