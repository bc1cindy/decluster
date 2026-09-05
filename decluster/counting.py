"""Per-transaction W(E) count provider.

Thin delegate to `dss.w_count` — the crate's feasibility-cascade dispatcher (brute -> dp -> sparse ->
sasamoto), which picks the counting method by feasibility and returns the best-available guarantee
plus the method used. Method SELECTION is the dss caller-toolkit's job (done once, in Rust, beside the
regime logic and with cross-validated tests); decluster just consumes the unified result. Counts are
weight-of-evidence, not a score, and an off-regime or panicking call must never fabricate a count.
"""

_UNKNOWN = {"kind": "unknown", "count": None, "log_w": None}

# The tiers that carry a guarantee of not exceeding the true multiplicity. The saddle-point
# estimate is not among them: it errs in both directions.
_GUARANTEED = frozenset({"exact", "lowerbound"})


def guaranteed_log_w(count):
    """`log_w`, but only from a tier guaranteed not to overstate the count; else None.

    An over-estimate of W(E) inflates whatever consumes it — it credits a coin with counterfactual
    paths the transaction may not admit, and a reported anonymity built on those is privacy the
    holder does not have. Undercounting is the safe direction: a path the adversary failed to see
    is still a path. So an approximate or unrecognised tier is refused here rather than discounted,
    and the caller falls back to multiplicity 1.
    """
    kind = str(count.get("kind", "")).strip().lower().replace("_", "").replace("-", "")
    return count.get("log_w") if kind in _GUARANTEED else None


# The cascade's brute branch enumerates *every* distinct output subset sum as a target and, for each,
# every input subset at every size. Its own width limit is twenty inputs, and that is exactly where
# the call stops returning: probed per width on a real slice, under a second to ten inputs, 3.4s at
# sixteen, and past twenty two thirds of the transactions never finished. A hang is not an exception,
# so the panic guard below cannot catch it, and a Python alarm cannot either, the block being inside
# Rust — the only bound available is declining the call.
#
# Sixteen is the largest width the slice both contains and completes, and it keeps the dense 16-input
# mix the cascade is pinned to count exactly. Widths seventeen to nineteen do not occur in the
# measured data, so the cliff sits between 16 and 20 and no more precisely than that.
#
# This limit belongs to the whole-transaction count only. `per_coin_log_w` below reaches the same
# crate through its fee-aware per-coin path, which returns in milliseconds at sixty-seven inputs and
# needs no such guard.
MAX_INPUTS = 16


def w_total(inputs, outputs, max_size=MAX_INPUTS):
    """Total subset-sum multiplicity W(E) of ONE transaction (a per-target subset count, NOT
    Maurer's full matched-partition mapping count |M| nor a mapping-entropy), as {"kind", "count", "log_w",
    "method"}. Delegates to `dss.w_count`, which cascades the four exact/approx counting primitives by
    feasibility (brute for tiny N, exact DP, sparse convolution, then the Sasamoto saddle-point for the
    Dense regime) and returns the strongest guarantee available — Exact where tractable, a LowerBound
    where the exact count saturates, a LogApprox in the large Dense regime, else unknown.

    `max_size` caps the input count the call is attempted on; above it the answer is `unknown`,
    which every consumer already reads as multiplicity 1. Undercounting is the safe direction for a
    refuse-only channel, and a wide transaction is where the count would be least trustworthy
    anyway. Lazy `import dss`; panic-safe (dss can hard-panic on pathological inputs) — never
    crash, and never hang, on a count.

    Fee-blind by construction: it asks which input subsets hit an output subset sum *exactly*, and a
    real transaction pays a fee, so no subset balances and the answer is an exact zero. On a 1,428
    transaction slice that is 1,223 of the 1,303 exact counts. An exact zero is the counter running
    to completion and finding nothing, which is the weakest corroboration available, not the
    strongest — see `cost.amount_cuts`. Use `per_coin_log_w` for a fee-aware reading."""
    inputs, outputs = list(inputs), list(outputs)
    if len(inputs) > max_size:
        return dict(_UNKNOWN)
    import dss

    try:
        return dss.w_count(inputs, outputs)
    except BaseException:
        return dict(_UNKNOWN)


def per_coin_log_w(inputs, outputs):
    """Per-coin ambiguity from the crate's fee-aware path: `{index: log_w}` over the input coins.

    `w_total` above answers a whole-transaction question, fee-blind and bounded by width. This is
    the measurement `cost.amount_cuts` already consumes: a knee-truncated lower bound on each coin's
    own ambiguity, computed against the transaction's actual balance rather than an exact subset
    hit, and returning in milliseconds at widths where the whole-transaction count does not return
    at all. Coins the truncation could not reach are absent rather than zero.

    A low value flags a candidate — few small balancing subsets were found — and never proves low
    ambiguity, since a real balance may need more coins than the truncation counts.
    """
    import dss

    try:
        report = dss.per_coin_density(list(inputs), list(outputs))
    except BaseException:
        return {}
    out = {}
    for coin in report.get("coins", ()):
        if coin.get("role") != "in":
            continue
        lw = coin.get("log_w")
        if lw is not None and lw == lw and lw not in (float("inf"), float("-inf")):
            out[coin["index"]] = lw
    return out


# The crate's own knee for coinjoin-shaped analysis. Bounding the subset size is what makes the
# convolution safe at width: unbounded, it builds the graded sumset up to N and a 25-input
# transaction takes minutes; at the knee the same call returns in milliseconds.
KNEE = 5


def count_w(inputs, outputs, knee=KNEE, radix_first=True, sparse_max=50):
    """Route one transaction to the counting method that suits it, returning the dss shape plus the
    `method` that answered.

    The order is the one the design calls for, and it deliberately does not include brute force,
    which is the same algorithm as the convolution below its crossover:

      radix     an output-only structural diagnostic, used only where amounts actually decompose
                into repeated denominations. The crate hands back a number whether or not they do,
                so that precondition is checked here by `radix_applies`. It is not a bound on the
                transaction's mapping count. Unguarded it answers on 37% of real transactions
                and 95.7% of those are not denominated at all.
      sparse    the subset-sum solution count W(E), bounded by `knee`. It is exact where it can be
                and otherwise a lower bound on W(E), not on the subtransaction mapping count.

    The saddle-point estimator is deliberately not a third tier, and the reason is narrow: it does
    not fill the holes a truncated lower bound leaves, so chaining it as an automatic upgrade mixes
    two different readings into one number. That composition was built upstream and withdrawn. It is
    still available here as `saddle_point_log_w`, to be asked for on purpose — an analyst reading a
    confirmed transaction may well want a magnitude estimate, and the estimator is useful beyond the
    construction side.

    Brute force is absent for a different reason: it is the same algorithm as the convolution below
    its crossover, so it adds a way to be slow and no way to be right.

    `sparse_max` bounds the convolution by input width. The knee alone is nearly enough — it takes
    a 25-input call from minutes to milliseconds — but one 67-input transaction in the measured
    slice still ran 81s, so a residual width guard stays.

    Contrast `w_total`, which delegates to the crate's own cascade: that tries brute first and
    hands the convolution an unbounded subset size, which is why it does not return past twenty
    inputs. Nothing here is a privacy score; a count that did not resolve reads as `unknown`, and
    every consumer treats that as multiplicity 1.
    """
    inputs, outputs = list(inputs), list(outputs)
    if not inputs or not outputs:
        return dict(_UNKNOWN, method="none")
    import dss

    if radix_first and radix_applies(outputs):
        r = _resolved(lambda: dss.radix_mappings(outputs, knee))
        if r is not None:
            return dict(r, method="radix")
    if len(inputs) <= sparse_max:
        r = _resolved(lambda: dss.w_sparse(inputs, outputs, knee))
        if r is not None:
            return dict(r, method="sparse")
    return dict(_UNKNOWN, method="none")


def _resolved(call):
    """The counter's answer, or None when it did not actually resolve anything.

    A tier that completes with a count of zero has found no mapping at all, which is the absence of
    an answer and not an answer of "no ambiguity" — the same distinction `cost.amount_cuts` draws
    for an unreachable coin. Treating it as resolved would let the first tier short-circuit the rest
    on a non-result: the radix path returns an exact zero on 63% of real multi-input transactions.
    """
    try:
        r = call()
    except BaseException:
        return None
    if str(r.get("kind", "")).lower() == "unknown":
        return None
    if (r.get("count") or 0) == 0 and r.get("log_w") is None:
        return None
    return r


def is_dense(inputs, outputs):
    """Whether the per-coin gate reads this instance as Dense, as `kappa < kappa_c`.

    This is the *optimistic* reading: the exposed kappa is computed at the best-case L, while the
    saddle-point's own gate requires kappa < kappa_c at the WORST-case L and calls anything between
    the two Transitional. So a True here does not promise that the saddle point will answer, and in
    practice it usually does not. Reported so the discrepancy is visible rather than surprising.
    """
    import dss

    try:
        report = dss.per_coin_density(list(inputs), list(outputs))
    except BaseException:
        return None
    coins = [c for c in report.get("coins", ()) if c.get("role") == "in"]
    if not coins:
        return None
    kappa_c = sum(c["kappa_c"] for c in coins) / len(coins)
    return report["kappa"] < kappa_c


def saddle_point_log_w(inputs, outputs):
    """`log W(E)` from the saddle point, or None where it does not apply. Not a fallback.

    Deliberately separate from `count_w`'s routing rather than a tier inside it. It estimates a
    magnitude where the exact tiers return a truncated lower bound, and those are different
    readings: substituting one for the other silently would let an estimate stand where a guaranteed
    floor was asked for. Ask for it when an estimate is what you want.

    It applies only in the Dense regime and declines everywhere else, which on real transactions is
    almost everywhere — see `is_dense`, and note that the gate it applies internally is stricter
    than the one that function reports.
    """
    import dss

    try:
        report = dss.w_sasamoto(list(inputs), list(outputs))
    except BaseException:
        return None
    if str(report.get("kind", "")).lower() == "unknown":
        return None
    return report.get("log_w")


# A denomination has to repeat before its permutations bound anything. Three is the same floor the
# de-mix uses to call a value a mix denomination.
RADIX_MIN_MULTIPLICITY = 3

# The bases the denominational decomposition is stated over. A value of Hamming weight one in one of
# them is a single digit times a power of that base -- 5,000,000 in base ten, 2^20 in base two.
RADIX_BASES = (2, 3, 10)


def radix_series(value, bases=RADIX_BASES):
    """`(base, exponent, digit)` when `value` is a single digit times a power of one of `bases`,
    else None. That is what "Hamming weight one" names: one non-zero digit in that base."""
    if value <= 0:
        return None
    for base in bases:
        v, exponent = value, 0
        while v % base == 0:
            v //= base
            exponent += 1
        if v < base and exponent:
            return (base, exponent, v)
    return None


def radix_applies(outputs, min_multiplicity=RADIX_MIN_MULTIPLICITY, bases=RADIX_BASES):
    """Whether the denominational lower bound is valid for these outputs.

    The bound counts the ways a repeated denomination can be permuted among the participants, so it
    means nothing unless a denomination actually repeats. The crate computes it either way and
    leaves this precondition to the caller; unguarded, it answers on 37% of real multi-input
    transactions and 95.7% of those carry no repeated value at all.

    Following the classification the upstream work describes: separate the values into multiplicity
    counts per *kind* of value, and take the low-Hamming-weight ones seriously. A value that is not
    a single digit times a power of one of the bases is not a denomination, however often it
    repeats, so counting its repeats towards the bound would be counting the wrong thing.

    The gap analysis within a series is the remaining half and stays upstream; it would only narrow
    this further, never widen it.
    """
    counts = {}
    for value in outputs:
        series = radix_series(value, bases)
        if series is not None:
            counts[value] = counts.get(value, 0) + 1
    return bool(counts) and max(counts.values()) >= min_multiplicity


# The link matrix is the one path here that tolerates a real fee: it reads the transaction's actual
# balance rather than asking for an exact subset hit, and answers at fees where the counts do not.
# No budget by default. The crate treats a budget as a *replacement* for its own size guard, and
# the budget is cooperative — it does not preempt an enumeration that has already blown up, which is
# why a subprocess variant exists for the walk. Passing none keeps the guard, which refuses the wide
# transactions instead of running into them.
DEFAULT_LINK_BUDGET_MS = None


def link_matrix(inputs, outputs, budget_ms=DEFAULT_LINK_BUDGET_MS, wall_ms=None):
    """The link-probability matrix, `m[i][j]` for input `i` against output `j`, or None.

    Rows say which outputs an input could plausibly have funded *under dss's mapping family*, and a
    row of ones is the case where every output is equally possible.

    A row with one non-zero entry is NOT a settled assignment. dss's family is a strict restriction
    of the exact balanced-mapping family, and this matrix is the uniform marginal over the smaller
    one, so it can put zero where the exact marginal is positive. Measured against the exact oracle
    over a 507-transaction family (`results/RESULTS-exact-oracle-audit.md`), reading a one-entry row
    as certain asserts 945 certainties the amounts do not settle, across 328 of those 507, while
    missing no genuinely certain link. The reading is an upper bound on certainty, not a proof of it.

    This is reachable from the amount channel, and unlike the counts it does not go quiet the moment
    a transaction pays a fee. It is no longer the provenance walk's transition measure: that walk
    defaults to `ancestry.value_flow_link_oracle` and reaches this only when a caller passes
    `ancestry.dss_link_oracle` or `oracle.bounded_dss_link_oracle()` explicitly.

    `budget_ms` replaces the crate's size guard rather than joining it, and neither bounds the cost
    in practice: measured, a single call under the guard alone ran past a minute. Bulk work needs
    `wall_ms`, which routes through the throwaway-subprocess oracle and kills on a real deadline —
    the same escape the provenance walk already keeps for this.
    """
    if wall_ms is not None:
        from .oracle import subprocess_link_oracle
        return subprocess_link_oracle(list(inputs), list(outputs), wall_ms)
    import dss

    try:
        return dss.pairwise_link_prob(list(inputs), list(outputs), budget_ms)
    except BaseException:
        return None


def link_ambiguity(inputs, outputs, budget_ms=DEFAULT_LINK_BUDGET_MS, wall_ms=None):
    """`{input index: how many outputs it could plausibly have funded}`, or {} when unresolved.

    One means the amounts determine where that input went. The count is what the row of the matrix
    carries, so it is on the same footing across coins of the same transaction.
    """
    matrix = link_matrix(inputs, outputs, budget_ms, wall_ms)
    if not matrix:
        return {}
    return {i: sum(1 for p in row if p > 0) for i, row in enumerate(matrix)}


def mapping_entropy(inputs, outputs, budget_ms=DEFAULT_LINK_BUDGET_MS):
    """Entropy over DSS's restricted mapping family and the links that family agrees on.

    `{"entropy": bits, "n_non_derived": int, "deterministic_links": [(input, output)]}`, or None
    where the enumeration is refused. The returned distribution is uniform over DSS's non-derived
    mappings. It is not the full balanced-mapping space and not an ownership posterior. The exact
    oracle audit shows that certainty in this family can be false in the larger family.

    Fee handling is the same as the link matrix: the fee is balanced in as an extra output before
    enumerating, so it answers on transactions where an exact-cancellation count cannot. Zero bits
    means one reading survives in this family; a deterministic link is shared by every mapping in
    this family. Neither statement is a global ownership proof.
    """
    import dss

    try:
        report = dss.mapping_analysis(list(inputs), list(outputs), budget_ms)
    except BaseException:
        return None
    if not isinstance(report, dict) or report.get("status") != "complete":
        return None
    return report
