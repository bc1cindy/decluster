"""Layer 3 — Fellegi-Sunter combiner: score(txA,txB) in bits (+ same / - different)."""
import math
from collections import Counter
from .extractors import x_nsequence, x_input_order
from .engine import sample_recent_txs

def _locktime_policy(tx): return "zero" if tx["locktime"] == 0 else "height"

AXES = {"nsequence": x_nsequence, "locktime": _locktime_policy, "in_order": x_input_order}

_LIB_AXIS = {"nsequence": "nsequence", "in_order": "input_order", "locktime": "locktime"}

class Combiner:
    def __init__(self, sample=None, consistency=0.95):
        self.c = consistency
        sample = sample or sample_recent_txs()
        self.freq, self.collision = {}, {}
        for name, fn in AXES.items():
            cnt = Counter(fn(tx) for tx, _ in sample); tot = sum(cnt.values())
            self.freq[name] = {v: k/tot for v, k in cnt.items()}
            self.collision[name] = sum((k/tot)**2 for k in cnt.values())
        self.n = len(sample)

    @classmethod
    def from_library(cls, consistency=0.95):
        """Build from the measured library bits (library.py) rather than a live sample."""
        from .library import _BY
        self = cls.__new__(cls)
        self.c = consistency
        self.freq, self.collision = {}, {}
        for name in AXES:
            bits = (_BY.get(_LIB_AXIS[name]) or {}).get("bits") or {}
            p = {v: 2 ** -b for v, b in bits.items() if b > 0}   # drop 0-bit abstain values (p=1 would poison collision)
            if name == "locktime":   # combiner uses zero/height; aggregate height_*
                ph = sum(pv for v, pv in p.items() if v != "zero")
                p = {"zero": p.get("zero", 0.5), "height": ph or 0.5}
            self.freq[name] = p
            self.collision[name] = sum(pv * pv for pv in p.values())
        self.n = 1000   # effective population for the unseen-value floor
        return self

    def score(self, txA, txB, explain=False):
        total, rows = 0.0, []
        for name, fn in AXES.items():
            va, vb = fn(txA), fn(txB)
            if name == "in_order" and ({"single", "small_n"} & {va, vb}):
                rows.append((name, va, vb, None)); continue   # order uninformative (n=1, or small-n sorted -> coincidental)
            if va == vb:
                w = -math.log2(self.freq[name].get(va, 1/self.n))
            else:
                w = min(0.0, math.log2((1 - self.c) / max(1 - self.collision[name], 1e-6)))
            total += w; rows.append((name, va, vb, w))
        return (total, rows) if explain else total

def verdict(bits):
    if bits >= 3:  return f"SAME wallet (strong, {bits:+.1f} bits)"
    if bits > 0:   return f"same (weak, {bits:+.1f} bits)"
    if bits > -3:  return f"different (weak, {bits:+.1f} bits)"
    return f"DIFFERENT wallets (strong, {bits:+.1f} bits)"
