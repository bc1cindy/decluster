"""Layer 3 — Fellegi-Sunter combiner: score(txA,txB) in bits (+ same / - different)."""
import math
from collections import Counter
from .extractors import x_nsequence, x_input_order, locktime_policy
from .engine import sample_recent_txs

AXES = {"nsequence": x_nsequence, "locktime": locktime_policy, "in_order": x_input_order}
_LIB_AXIS = {"nsequence": "nsequence", "in_order": "input_order", "locktime": "locktime"}

def _never(va, vb): return False
def _in_order_abstain(va, vb): return bool({"single", "small_n"} & {va, vb})
_ABSTAIN = {"nsequence": _never, "locktime": _never, "in_order": _in_order_abstain}

def fs_score(axes, txA, txB, c, floor_n, explain=False):
    """Fellegi-Sunter kernel over axes = [(name, fn, p, collision, abstain)]: agreement adds
    -log2(p[value]); a mismatch adds a clamped (<=0) weight; abstain(va, vb) skips the axis.
    c is a float, or a dict mapping axis-name -> m per axis (must cover every scored axis)."""
    total, rows = 0.0, []
    for name, fn, p, collision, abstain in axes:
        va, vb = fn(txA), fn(txB)
        if abstain(va, vb):
            rows.append((name, va, vb, None)); continue
        if va == vb:
            w = -math.log2(p.get(va, 1.0 / floor_n))
        else:
            cj = c[name] if isinstance(c, dict) else c
            w = min(0.0, math.log2((1 - cj) / max(1 - collision, 1e-6)))
        total += w; rows.append((name, va, vb, w))
    return (total, rows) if explain else total

class Combiner:
    def __init__(self, sample=None, consistency=0.95):
        self.c = consistency
        sample = sample or sample_recent_txs()
        self.axes = []
        for name, fn in AXES.items():
            cnt = Counter(fn(tx) for tx, _ in sample); tot = sum(cnt.values())
            p = {v: k / tot for v, k in cnt.items()}
            collision = sum((k / tot) ** 2 for k in cnt.values())
            self.axes.append((name, fn, p, collision, _ABSTAIN[name]))
        self.floor_n = len(sample)

    @classmethod
    def from_library(cls, consistency=0.95):
        """Build from the measured library bits (library.py) rather than a live sample."""
        from .library import _BY
        self = cls.__new__(cls)
        self.c = consistency
        self.axes = []
        for name, fn in AXES.items():
            bits = (_BY.get(_LIB_AXIS[name]) or {}).get("bits") or {}
            p = {v: 2 ** -b for v, b in bits.items() if b > 0}   # drop 0-bit abstain values
            if name == "locktime":   # locktime_policy emits zero/height; fold all non-zero into height
                ph = sum(pv for v, pv in p.items() if v != "zero")
                p = {"zero": p.get("zero", 0.5), "height": ph or 0.5}
            collision = sum(pv * pv for pv in p.values())
            self.axes.append((name, fn, p, collision, _ABSTAIN[name]))
        self.floor_n = 1000
        return self

    def score(self, txA, txB, explain=False):
        return fs_score(self.axes, txA, txB, self.c, self.floor_n, explain)

def verdict(bits):
    if bits >= 3:  return f"SAME wallet (strong, {bits:+.1f} bits)"
    if bits > 0:   return f"same (weak, {bits:+.1f} bits)"
    if bits > -3:  return f"different (weak, {bits:+.1f} bits)"
    return f"DIFFERENT wallets (strong, {bits:+.1f} bits)"
