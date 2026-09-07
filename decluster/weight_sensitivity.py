"""Sensitivity of attacker-side fingerprint evidence to one global weight."""

from __future__ import annotations

import math

from .fingerprint_validate import LibraryScorer, evaluate

GRID = (0.60, 0.70, 0.80, 0.90, 0.95, 0.99)


def sweep(transactions, *, pair_cap=4000, seed=0):
    """Evaluate one deterministic pair sample at each global consistency value."""
    rows = []
    for consistency in GRID:
        measurement = evaluate(
            transactions,
            LibraryScorer(consistency=consistency),
            cap=pair_cap,
            seed=seed,
        )
        rows.append({"consistency": consistency, **measurement})
    decrements = [left["auc"] - right["auc"]
                  for left, right in zip(rows, rows[1:]) if left["auc"] > right["auc"]]
    largest = max(decrements, default=0.0)
    error = auc_standard_error(max(row["auc"] for row in rows), pair_cap, pair_cap)
    return {
        "transactions": len(transactions),
        "pair_cap_per_class": pair_cap,
        "seed": seed,
        "rows": rows,
        "realistic_band_auc_range": max(row["auc"] for row in rows[3:])
        - min(row["auc"] for row in rows[3:]),
        "auc_is_monotone_non_decreasing": all(
            left["auc"] <= right["auc"] for left, right in zip(rows, rows[1:])
        ),
        # A dip in the measured sequence is a fact about these numbers; whether it says anything
        # about the underlying ordering depends on how it compares to what the sample resolves.
        "auc_standard_error": error,
        "largest_decrement": largest,
        "largest_decrement_in_standard_errors": (largest / error) if error else None,
    }

def auc_standard_error(auc, positives, negatives):
    """Hanley-McNeil standard error of an AUC, so a difference can be read against its resolution.

    Without it a sweep reports that the measured sequence dips and a reader has no way to tell a
    real reversal from sampling noise. On this grid the largest dip is a fifth of one standard
    error, which does not falsify a monotone ordering; it fails to support one.
    """
    if not positives or not negatives:
        return None
    q1 = auc / (2 - auc)
    q2 = 2 * auc ** 2 / (1 + auc)
    variance = (auc * (1 - auc)
                + (positives - 1) * (q1 - auc ** 2)
                + (negatives - 1) * (q2 - auc ** 2)) / (positives * negatives)
    return math.sqrt(max(variance, 0.0))
