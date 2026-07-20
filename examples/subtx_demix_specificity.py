"""Specificity of the coinjoin de-mix on ordinary (unlabelled) transactions. Measures, over a sample
of local multi-input txs, how many the de-mix recovers any participant from (expected ~0 on ordinary
batch/payment txs). Reads txs from a local cache dir (CACHE env, default .cache — a dir of JSON tx
files with vin[].prevout and vout[]). Run: python3 examples/subtx_demix_specificity.py"""
import glob
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decluster.coinjoin_demix import coinjoin_demix

CACHE = os.environ.get("CACHE", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache"))
SAMPLE = int(os.environ.get("SAMPLE", "300"))


def recovers_any(ins, outs):
    return len(coinjoin_demix(ins, outs)) > 0


def run():
    files = glob.glob(os.path.join(CACHE, "*"))
    if not files:
        print(f"no tx files under {CACHE} (set CACHE)"); return
    random.Random(0).shuffle(files)
    tested = hits = 0
    for f in files:
        if tested >= SAMPLE:
            break
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        vin, vout = d.get("vin"), d.get("vout")
        if not vin or not vout or not all("prevout" in v for v in vin):
            continue
        ins = [v["prevout"]["value"] for v in vin]
        outs = [o["value"] for o in vout]
        if len(ins) < 3 or len(ins) > 60 or len(outs) < 2:
            continue
        tested += 1
        if recovers_any(ins, outs):
            hits += 1
    if not tested:
        print(f"no multi-input txs found under {CACHE}"); return
    print(f"# {tested} local multi-input txs (3-60 inputs) from {CACHE}\n")
    print(f"de-mix recovers a participant in {hits}/{tested} ordinary local txs")


if __name__ == "__main__":
    run()
