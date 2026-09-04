"""Exact-vector class sizes for transaction-construction fingerprints."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping

LABELS = (
    "exactly 1",
    "2-9",
    "10-99",
    "100-999",
    "1,000-9,999",
    "10,000-99,999",
    ">=100,000",
)


def bucket(size: int) -> str:
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise ValueError("class size must be a positive integer")
    if size == 1:
        return LABELS[0]
    for index, upper in enumerate((10, 100, 1_000, 10_000, 100_000), start=1):
        if size < upper:
            return LABELS[index]
    return LABELS[-1]


def distribution(counts: Mapping[object, int]):
    """Return transaction-weighted class-size shares and the transaction count."""
    histogram = Counter()
    for size in counts.values():
        if isinstance(size, bool) or not isinstance(size, int) or size < 1:
            raise ValueError("vector occurrence counts must be positive integers")
        histogram[bucket(size)] += size
    total = sum(histogram.values())
    if total == 0:
        raise ValueError("at least one vector occurrence count is required")
    return {label: histogram.get(label, 0) / total for label in LABELS}, total


def reconstruct_histogram(conditional: Mapping[str, Mapping[str, object]]):
    """Recover a global histogram from a partition of conditional bucket counts."""
    histogram = Counter()
    if not conditional:
        raise ValueError("conditional partition must not be empty")
    for value, record in conditional.items():
        if not isinstance(record, Mapping) or not isinstance(record.get("buckets"), Mapping):
            raise ValueError(f"conditional value {value!r} has no bucket mapping")
        unknown = set(record["buckets"]) - set(LABELS)
        if unknown:
            raise ValueError(f"conditional value {value!r} has unknown buckets: {sorted(unknown)}")
        for label, count in record["buckets"].items():
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError(f"bucket {label!r} for {value!r} has an invalid count")
            histogram[label] += count
    total = sum(histogram.values())
    if total == 0:
        raise ValueError("conditional partition contains no transactions")
    return {label: histogram.get(label, 0) for label in LABELS}, total
