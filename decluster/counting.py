"""Per-transaction W(E) count provider.

Thin delegate to `dss.w_count` — the crate's feasibility-cascade dispatcher (brute -> dp -> sparse ->
sasamoto), which picks the counting method by feasibility and returns the best-available guarantee
plus the method used. Method SELECTION is the dss caller-toolkit's job (done once, in Rust, beside the
regime logic and with cross-validated tests); decluster just consumes the unified result. Counts are
weight-of-evidence, not a score, and an off-regime or panicking call must never fabricate a count.
"""

_UNKNOWN = {"kind": "unknown", "count": None, "log_w": None}


def w_total(inputs, outputs, max_size=64):
    """Total subset-sum multiplicity W(E) of ONE transaction (a per-target subset count, NOT
    Maurer's full matched-partition mapping count |M| nor a mapping-entropy), as {"kind", "count", "log_w",
    "method"}. Delegates to `dss.w_count`, which cascades the four exact/approx counting primitives by
    feasibility (brute for tiny N, exact DP, sparse convolution, then the Sasamoto saddle-point for the
    Dense regime) and returns the strongest guarantee available — Exact where tractable, a LowerBound
    where the exact count saturates, a LogApprox in the large Dense regime, else unknown. `max_size` is
    accepted for backward compatibility and ignored (the dispatcher self-selects). Lazy `import dss`;
    panic-safe (dss can hard-panic on pathological inputs) — never crash on a count."""
    import dss

    try:
        return dss.w_count(list(inputs), list(outputs))
    except BaseException:
        return dict(_UNKNOWN)
