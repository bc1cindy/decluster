"""Distribution drift and volume coupling across graph-view epochs."""

from __future__ import annotations

import math

GAPS = (1, 2, 3, 7, 14, 21, 30, 60, 90, 120)
CYCLE = 7


def normalise(counts):
    total = sum(counts.values())
    return {key: value / total for key, value in counts.items()} if total else {}


def total_variation(left, right):
    return 0.5 * sum(
        abs(left.get(key, 0.0) - right.get(key, 0.0))
        for key in set(left) | set(right)
    )


def pearson(left, right):
    if len(left) != len(right) or not left:
        raise ValueError("Pearson inputs must have the same non-zero length")
    mean_left = sum(left) / len(left)
    mean_right = sum(right) / len(right)
    numerator = sum(
        (x - mean_left) * (y - mean_right)
        for x, y in zip(left, right)
    )
    denominator = math.sqrt(
        sum((x - mean_left) ** 2 for x in left)
        * sum((y - mean_right) ** 2 for y in right)
    )
    return numerator / denominator if denominator else 0.0


def drift(series, gaps):
    return {
        gap: sum(
            total_variation(series[index], series[index + gap])
            for index in range(len(series) - gap)
        ) / (len(series) - gap)
        for gap in gaps
        if 0 < gap < len(series)
    }


def cycle_gain(series, span=3):
    """Compare mean drift on weekly-cycle gaps with other gaps in the same range."""
    if isinstance(span, bool) or not isinstance(span, int) or span < 1:
        raise ValueError("cycle span must be a positive integer")
    curve = drift(series, range(1, CYCLE * span + 1))
    on_cycle = [value for gap, value in curve.items() if gap % CYCLE == 0]
    off_cycle = [value for gap, value in curve.items() if gap % CYCLE]
    if not on_cycle or not off_cycle:
        raise ValueError("series is too short for the requested cycle span")
    baseline = sum(off_cycle) / len(off_cycle)
    return (sum(on_cycle) / len(on_cycle)) / baseline if baseline else 1.0
