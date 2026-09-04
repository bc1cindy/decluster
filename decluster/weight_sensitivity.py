"""Sensitivity of attacker-side fingerprint evidence to one global weight."""

from __future__ import annotations

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
    }
