"""Layer 3 — legacy value-rarity fingerprint combiner.

Agreement is weighted by observed value rarity and disagreement by a supplied
consistency assumption.  Existing callers retain this behavior.  The fitted,
supervised Fellegi--Sunter baseline lives in :mod:`decluster.fellegi_sunter`.
"""
import math
import warnings
from collections import Counter
from .extractors import NA, x_nsequence, x_input_order, locktime_policy
from .engine import sample_recent_txs

# A fixed three-axis choice, not the output of a selection procedure. Checked afterwards rather
# than chosen for it: within-class phi over these three peaks at 0.125 (nsequence/locktime,
# non-match class), so the additive kernel is not double-counting here. In the match class phi is
# undefined — locktime and in_order agree on every scored match pair, so a marginal is degenerate.
# That the triple is uncorrelated is a property of this particular triple, not of the method.
AXES = {"nsequence": x_nsequence, "locktime": locktime_policy, "in_order": x_input_order}
_LIB_AXIS = {"nsequence": "nsequence", "in_order": "input_order", "locktime": "locktime"}

def _absent(va, vb): return NA in (va, vb)
def _in_order_abstain(va, vb): return _absent(va, vb) or bool({"single", "small_n"} & {va, vb})
# Every axis abstains where the export does not say; `NA` is never a value two transactions can
# agree on.
_ABSTAIN = {"nsequence": _absent, "locktime": _absent, "in_order": _in_order_abstain}

def rarity_score(axes, txA, txB, c, floor_n, explain=False):
    """Legacy rarity kernel over axes = [(name, fn, p, collision, abstain)]: agreement adds
    -log2(p[value]); a mismatch adds a clamped (<=0) weight; abstain(va, vb) skips the axis.
    c is a float, or a dict mapping axis-name -> m per axis (must cover every scored axis)."""
    total, rows = 0.0, []
    for name, fn, p, collision, abstain in axes:
        va, vb = fn(txA), fn(txB)
        if abstain(va, vb):
            rows.append((name, va, vb, None)); continue
        if va == vb:
            if va not in p:                     # value never measured -> rarity unknown, not evidence
                rows.append((name, va, vb, None)); continue   # (crediting -log2(1/floor_n) would forge a match)
            w = -math.log2(p[va])
        else:
            cj = c[name] if isinstance(c, dict) else c
            w = min(0.0, math.log2((1 - cj) / max(1 - collision, 1e-6)))
        total += w; rows.append((name, va, vb, w))
    return (total, rows) if explain else total


def fs_score(axes, txA, txB, c, floor_n, explain=False):
    """Compatibility wrapper for the former, misleading function name."""
    warnings.warn(
        "fs_score is a rarity baseline, not fitted Fellegi-Sunter; use rarity_score",
        DeprecationWarning,
        stacklevel=2,
    )
    return rarity_score(axes, txA, txB, c, floor_n, explain)

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
        from .library import _BY, p_from_bits
        self = cls.__new__(cls)
        self.c = consistency
        self.axes = []
        for name, fn in AXES.items():
            p = p_from_bits((_BY.get(_LIB_AXIS[name]) or {}).get("bits"))
            if name == "locktime":   # locktime_policy emits zero/height; fold all non-zero into height
                ph = sum(pv for v, pv in p.items() if v != "zero")
                p = {"zero": p.get("zero", 0.5), "height": ph or 0.5}
            collision = sum(pv * pv for pv in p.values())
            self.axes.append((name, fn, p, collision, _ABSTAIN[name]))
        self.floor_n = 1000
        return self

    def score(self, txA, txB, explain=False):
        return rarity_score(self.axes, txA, txB, self.c, self.floor_n, explain)
