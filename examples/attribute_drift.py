"""Stability of construction-fingerprint attributes across epochs.

Cross-view matching compares a vertex's statistical attributes between two views built
from different epochs. That is only sound if the attribute means the same thing in both.
Three ways it does not, measured here:

  drift vs gap   total-variation distance between two epochs' axis distributions against
                 how far apart they are. A curve that keeps rising is a secular trend and
                 bounds how far the views may be separated.
  weekly cycle   epochs are ~1 day, so gaps that are multiples of 7 compare like weekdays
                 with like. If those gaps sit below their neighbours, view separation
                 should be chosen on the cycle rather than merely "close together".
  common mode    how much of a value's movement tracks epoch transaction volume, a global
                 covariate. Volume-coupled movement shifts every vertex the same way at
                 once, so it biases a raw cross-view comparison rather than merely adding
                 noise, and is what per-epoch normalisation removes.

usage: python3 examples/attribute_drift.py <epochs.jsonl>
"""
import json
import sys

from decluster.attribute_drift import (
    CYCLE,
    GAPS,
    cycle_gain,
    drift,
    normalise,
    pearson,
    total_variation,
)


def load(path):
    volume, axes = [], {}
    for line in open(path):
        d = json.loads(line)
        volume.append(d["txs"])
        for axis, counts in d["axis_counts"].items():
            axes.setdefault(axis, []).append(normalise(counts))
    return volume, axes


def main(path):
    volume, axes = load(path)
    n = len(volume)
    print(f"epochs: {n}  volume: {min(volume):,} to {max(volume):,} txs/epoch\n")

    print("total-variation distance between epoch distributions, by gap (epochs)")
    print("axis".ljust(22) + "".join(f"{g:>7}" for g in GAPS) + "   wk")
    curves, gains = {}, {}
    for axis, series in sorted(axes.items()):
        curves[axis] = drift(series, GAPS)
        gains[axis] = cycle_gain(series)
        print(axis.ljust(22) + "".join(f"{curves[axis][g]:7.3f}" for g in GAPS)
              + f"{gains[axis]:7.2f}")

    ratio = sorted(c[120] / c[1] for c in curves.values())
    print(f"\ngap-120 / gap-1: median {ratio[len(ratio) // 2]:.2f}, max {ratio[-1]:.2f}"
          "   (1.0 = no secular trend)")
    g = sorted(gains.values())
    print(f"weekly gain: median {g[len(g) // 2]:.2f}, best {g[0]:.2f}"
          "   (<1.0 = multiples of 7 are more comparable)")

    coupled = []
    for axis, series in sorted(axes.items()):
        for value in {k for s in series for k in s}:
            shares = [s.get(value, 0.0) for s in series]
            if sum(shares) / n <= 0.01:
                continue
            coupled.append((abs(pearson(volume, shares)), axis, value, sum(shares) / n))
    coupled.sort(reverse=True)
    print("\nstrongest volume coupling (values with mean share > 1%)")
    for r, axis, value, mean in coupled[:8]:
        print(f"  |r|={r:.3f}  r2={r * r:5.1%}  share={mean:6.2%}  {axis}={value[:32]}")
    strong = sum(1 for r, *_ in coupled if r > 0.5)
    med = sorted(r * r for r, *_ in coupled)[len(coupled) // 2]
    print(f"{strong}/{len(coupled)} values above |r| 0.5; median r2 {med:.1%}")

    worst = {}
    for r, axis, _, _ in coupled:
        worst[axis] = max(worst.get(axis, 0.0), r * r)
    print("\nshortlist for vertex attributes (stable at a one-week gap, weakly coupled)")
    rank = sorted(curves, key=lambda a: (curves[a][CYCLE], worst.get(a, 0.0)))
    for axis in rank[:6]:
        print(f"  TV@7={curves[axis][CYCLE]:.3f}  worst r2={worst.get(axis, 0.0):5.1%}  {axis}")
    print("  ...")
    for axis in rank[-3:]:
        print(f"  TV@7={curves[axis][CYCLE]:.3f}  worst r2={worst.get(axis, 0.0):5.1%}  {axis}")


if __name__ == "__main__":
    main(sys.argv[1])
