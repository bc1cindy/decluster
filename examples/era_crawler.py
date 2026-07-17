"""Stratified multi-era block crawler: fill .blkcache with a *balanced* sample across eras,
not the recent-skewed default. Targets evenly-spaced heights per era and pages each block
(capped), reusing fetch.py's cache + throttle. Idempotent (cached blocks are skipped).

usage: python3 -m examples.era_crawler [blocks_per_era] [max_pages_per_block]
"""
import sys, urllib.error
from decluster import fetch

SEGWIT, TAPROOT = 481824, 709632          # activation heights: SegWit (Aug 2017), Taproot (Nov 2021)
PRE_FLOOR = 200000                        # skip the near-empty earliest chain (~2012 onward)
ERAS = [("pre-segwit", PRE_FLOOR, SEGWIT), ("segwit", SEGWIT, TAPROOT), ("taproot", TAPROOT, None)]


def era(height):
    for name, lo, hi in ERAS:
        if lo <= height and (hi is None or height < hi):
            return name
    return "pre-floor"


def _targets(blocks_per_era, tip):
    """Evenly-spaced target heights inside each era (taproot capped at the current tip)."""
    out = []
    for name, lo, hi in ERAS:
        top = (tip if hi is None else hi) - 1
        if top <= lo:
            continue
        step = (top - lo) // blocks_per_era or 1
        out += [(name, lo + i * step) for i in range(blocks_per_era)]
    return out


def _crawl_block(height, max_pages):
    """Fetch up to max_pages*25 txs of the block at `height` into .blkcache. Returns tx count.
    Tolerant: a page past the block's end 404s (not []), which ends the block; a whole failed
    block is skipped (returns what was fetched so far)."""
    try:
        h = fetch.fetch_block_hash(height)
    except urllib.error.HTTPError:
        return 0
    got = 0
    for page in range(max_pages):
        try:
            txs = fetch.fetch_block_txs(h, page * 25)   # 25 per page
        except urllib.error.HTTPError as e:
            if e.code == 404:
                break                                    # past the last page -> end of block
            raise
        if not txs:
            break
        got += len(txs)
        if len(txs) < 25:
            break
    return got


def crawl(blocks_per_era=8, max_pages=8):
    tip = int(fetch.fetch_tip_height())
    targets = _targets(blocks_per_era, tip)
    tally = {name: 0 for name, _, _ in ERAS}
    for name, height in targets:
        n = _crawl_block(height, max_pages)
        tally[name] += n
        print(f"  {name:11} blk {height:>7} -> {n:4} txs")
    print("\nper-era txs fetched this run (cache-deduped across runs):")
    for name, _, _ in ERAS:
        print(f"  {name:11} {tally[name]}")
    return tally


if __name__ == "__main__":
    bpe = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    mp = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    print(f"stratified crawl: {bpe} blocks/era, up to {mp*25} txs/block\n")
    crawl(bpe, mp)
