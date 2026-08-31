"""Collect a UNIFORM ancestry sample for the definitive reid / ancestry-(epsilon,delta)-sparsity /
anonymity-set-at-scale measurements. Unlike the accreted `.cache/`, coins are sampled uniformly from
a block range, and each coin's depth-6 provenance signature is built with the REAL dss oracle via the
mempool.space API. Resumable: appends one {coin, sig} per line, skips coins already in the output.

usage: python3 examples/collect_ancestry.py <lo_height> <hi_height> <n_coins> <out.ndjson> [seed]
FETCH-BOUND and slow: measured ~70s+ per coin at depth 6 (wide ancestry pulls hundreds of ancestor txs via the API + an O(n^3) absorbing-Markov solve, capped by max_nodes). Budget ~a day for 500 coins, 2-4 days for 2000. Resumable — safe to stop/restart.
Suggested first run (a strong uniform sample, ~a day): 800000 810000 500 anc_uniform.ndjson
"""
import sys
import os
import json
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decluster.fetch import _get_text, fetch_block_txs, fetch_tx, API
from decluster.ancestry import build_extended_graph, absorber_distribution, dss_link_oracle


def sample_coins(lo, hi, n, seed=0):
    """Uniform-ish coin sample: random blocks in [lo, hi], their first-page txs, spendable outputs.
    Over-samples 3x so failed/empty walks can be dropped and still hit n."""
    rng = random.Random(seed)
    pool, tried = [], set()
    while len(pool) < n * 3 and len(tried) < (hi - lo + 1):
        h = rng.randint(lo, hi)
        if h in tried:
            continue
        tried.add(h)
        try:
            bhash = _get_text(f"{API}/block-height/{h}")
            txs = fetch_block_txs(bhash, 0)
        except Exception:
            continue
        for tx in txs:
            if any(v.get("is_coinbase") for v in tx.get("vin", [])):
                continue
            for i, o in enumerate(tx.get("vout", [])):
                if o.get("scriptpubkey_type") == "op_return":
                    continue
                pool.append((tx["txid"], i))
    rng.shuffle(pool)
    return pool[:n * 2]                      # keep a margin for walk failures


def signature(coin, depth, max_nodes):
    g = build_extended_graph(coin, depth=depth, fetch=fetch_tx, link_oracle=dss_link_oracle, max_nodes=max_nodes)
    return absorber_distribution(g, coin)


def main(lo, hi, n, out, seed=0, depth=6, max_nodes=600):
    done = set()
    if os.path.exists(out):
        for line in open(out):
            try:
                done.add(json.loads(line)["coin"])
            except Exception:
                pass
    print(f"resume: {len(done)} already collected", flush=True)
    coins = sample_coins(lo, hi, n, seed)
    kept = len(done)
    with open(out, "a") as f:
        for j, (txid, vout) in enumerate(coins):
            if kept >= n:
                break
            key = f"{txid}:{vout}"
            if key in done:
                continue
            try:
                sig = signature((txid, vout), depth, max_nodes)
            except Exception:
                continue
            if not sig:
                continue
            f.write(json.dumps({"coin": key, "sig": { (a if isinstance(a,str) else ":".join(map(str,a))): round(m, 8) for a, m in sig.items() }}) + "\n")
            f.flush()
            kept += 1
            if kept % 25 == 0:
                print(f"{kept}/{n} collected (scanned {j})", flush=True)
    print(f"done: {kept} signatures in {out}", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4],
         int(sys.argv[5]) if len(sys.argv) > 5 else 0)
