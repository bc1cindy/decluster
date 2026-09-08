"""Production approximations measured against the exact oracle.

`baselines.maurer` enumerates every balanced input/output block mapping of a transaction and
`baselines.boltzmann` averages over them uniformly.  That pair is the exact oracle: exponential,
zero-fee, and narrow.  The production paths — the compiled `dss` extension and the wrappers in
`decluster.counting`, `decluster.subtransaction` — are approximations of *something*, and nothing in
this repo measured which something, or in which direction the error runs.  This module does, over an
exhaustively enumerated family of small zero-fee transactions.

Semantics first, comparison second.  Comparing two quantities that count different objects
manufactures a defect that is really a category error, so every `dss` entry point used here is
identified before it is compared, and the identification is *re-derived in Python* by
`identify_objects` rather than taken from a docstring:

  exact ``|M|``            index-level balanced set partitions: every input and every output lies in
                           exactly one block, and every block conserves value on its own.  The
                           single-block (all coins, one owner) reading is included.
  ``dss.mapping_analysis`` refinement-maximal mappings on all 507 bounded cases checked here. This
                           is a strict sub-family of ``|M|`` on 491 cases. Equal-value permutations
                           do not collapse in general: ``[1,3,4,4] -> [3,3,3,3]`` answers 4.
                           Agreement with the refinement-maximal oracle is measured on this family,
                           not asserted universally.
  ``dss.pairwise_link_prob`` the uniform marginal over *that same restricted family*, not over the
                           oracle's.  Verified rather than argued, by
                           ``verify_dss_marginal_family``: on 507/507 cases every entry is an exact
                           multiple of ``1 / n_non_derived`` and the entries equal to 1.0 are
                           exactly the ``deterministic_links`` the same call reports.  So the
                           marginal, the count and the certain-link set are three outputs of one
                           enumeration and carry one classification: **restriction**.  A marginal
                           over a sub-family is neither a lower nor an upper bound on the marginal
                           over the full family, which is what the comparison then measures.
  ``dss.w_count`` /        NOT mappings.  Verified by re-derivation: the count is the number of
  ``w_brute`` / ``w_sparse``   non-empty proper input subsets whose sum equals some proper
                           output-subset sum — the subset-sum solution count ``W(E)``.  A set
                           partition is a simultaneous, disjoint, exhaustive choice of many such
                           subsets, so ``W(E)`` and ``|M|`` are different objects and ordering one
                           against the other says nothing about either.  Reported as an
                           identification, never as a count disagreement.
  ``dss.radix_mappings``   a function of the OUTPUT values alone; the inputs are not a parameter.
                           A quantity that cannot see the inputs cannot bound one that depends on
                           them.
  ``dss.per_coin_density`` per-coin ``log_w`` (natural log, not bits).  Measured on this family it
                           is invariant across every coin of a transaction, so it carries none of
                           the per-coin variation the exact marginals do carry.
  ``subtransaction.subtransactions`` ``ambiguity_bits`` over 2-in/2-out: ``log2`` of the number of
                           (receiver input, receiver output) pairs with a positive implied payment.
                           No block ever has to balance, so it is not a mapping count either.

Zero fee throughout.  The oracle has no fee model — it returns no mapping at all when the sides do
not balance — so nothing here speaks to how any of these behave on a fee-paying transaction, and the
`dss` link paths in particular balance a fee in as a synthetic extra output when there is one.

The relabelling above costs the finding nothing, and the audit also scores the link matrix against
the *finest-only* oracle family (mappings no other mapping strictly refines) so the result is
visibly independent of the oracle's inclusion of the single-block reading: the certain-link
overclaim is identical under both readings.

Every comparison carries a measured `bound_direction`.  "Lower bound" is a claim about all inputs,
and until something ran, no approximation in this repo had earned it.

Sources: `maurer` and `boltzmann` in `catalog/ctp-sources.json`. The pair is the exact
oracle the production approximations are measured against; neither is reimplemented here.
"""

from itertools import combinations, combinations_with_replacement

from .boltzmann import exact_link_analysis, exact_per_coin_link_evidence
from .maurer import (
    exact_subtransaction_mappings,
    non_derived_mappings,
)

FAMILY_ALPHABET = (1, 2, 3, 4)
FAMILY_MAX_COINS = 8
FAMILY_MIN_SIDE = 2
TOLERANCE = 1e-9

# Disagreements are counted in full; only the worked examples carried in the report are capped, so a
# 500-case family does not turn the summary into a case dump.
MAX_EXAMPLES = 12

# `radix_mappings` answers zero below this magnitude and non-zero at or above it, on output sets
# whose exact mapping count is identical either way. The scale is the demonstration, not a tuning.
RADIX_SCALE = 1000

# The results document this audit backs, and the source identity recorded for it. There is no data
# file behind these numbers — the family is generated — so the source is the exact enumerator,
# and the crate identity travels in the invariants, which is the half `check_manifest` compares.
MANIFEST_DOC = "RESULTS-exact-oracle-audit.md"
MANIFEST_SOURCE = "decluster/baselines/maurer.py"

# The comparability verdict attached to every probe. `restriction` means the approximation is the
# same quantity computed over a strict sub-family of what the oracle enumerates — comparable, so
# long as the restriction travels with the number, and a bound in neither direction by construction.
# `different-object` probes are identified and NOT compared. No probe here is over the same family,
# which is why there is no "same-object" verdict to assign.
RESTRICTION = "restriction"
DIFFERENT_OBJECT = "different-object"


def enumerate_family(alphabet=FAMILY_ALPHABET, max_coins=FAMILY_MAX_COINS,
                     min_side=FAMILY_MIN_SIDE):
    """Every balanced `(inputs, outputs)` over `alphabet` with both sides at least `min_side` coins
    and at most `max_coins` coins in total, each in canonical form exactly once.

    Canonical form is the pair of sorted value multisets: coin order carries no information the
    oracle reads, and `combinations_with_replacement` emits each multiset once per shape while
    distinct shapes differ in length, so nothing has to be deduplicated afterwards — a `seen` set
    here would be dead code, and a test asserts the result carries no duplicate.  Scale is
    deliberately NOT canonicalized — `|M|` is scale-invariant but
    `radix_mappings` and the density gate are not, so folding `(2,2)/(2,2)` into `(1,1)/(1,1)` would
    hide exactly the input dependence this audit is looking for.
    """
    return [
        (inputs, outputs)
        for n_in in range(min_side, max_coins - min_side + 1)
        for n_out in range(min_side, max_coins - n_in + 1)
        for inputs in combinations_with_replacement(alphabet, n_in)
        for outputs in combinations_with_replacement(alphabet, n_out)
        if sum(outputs) == sum(inputs)
    ]


def _proper_subset_sums(values):
    """Sums of the non-empty proper subsets of `values`, as a set."""
    return {
        sum(values[i] for i in subset)
        for size in range(1, len(values))
        for subset in combinations(range(len(values)), size)
    }


def _subset_sum_solutions(inputs, outputs):
    """`W(E)` re-derived: non-empty proper input subsets whose sum is a proper output-subset sum."""
    targets = _proper_subset_sums(outputs)
    return sum(
        1
        for size in range(1, len(inputs))
        for subset in combinations(range(len(inputs)), size)
        if sum(inputs[i] for i in subset) in targets
    )


def equal_value_mapping_count(n):
    """Self-derived closed form for `|M|` of an n-in/n-out join of one repeated value.

    Derivation (mine, from the oracle's own definition — not taken from any paper).  When every coin
    carries the same value, a block of `a` inputs balances exactly the blocks of `a` outputs, so a
    mapping is: a set partition of the inputs, a set partition of the outputs with the *same*
    multiset of block sizes, and a size-preserving bijection between the two.  Write a shape as
    sizes with multiplicities `m_s` (so 4 = 2+1+1 has `m_2 = 1, m_1 = 2`).  The set partitions of n
    labelled coins with that shape is the standard

        P(shape) = n! / (prod_s (s!)^{m_s} * prod_s m_s!)

    and the size-preserving bijections number `prod_s m_s!`, since blocks of equal size are
    interchangeable and blocks of different sizes cannot pair.  Hence

        |M|(n) = sum over shapes of  P(shape)^2 * prod_s m_s!

    n = 2 gives 1 + 2 = 3 (identity pairing, swapped pairing, single all-coins block), so the
    canonical equal-value 2-in/2-out join has three mappings and log2(3) = 1.585 bits of entropy.
    n = 3 gives 16 and n = 4 gives 131.  `tests/test_oracle_audit.py` checks the form against the
    oracle's own enumeration rather than trusting the algebra.
    """
    from math import factorial

    def shapes(remaining, largest):
        if not remaining:
            yield ()
            return
        for size in range(min(remaining, largest), 0, -1):
            for rest in shapes(remaining - size, size):
                yield (size,) + rest

    total = 0
    for shape in shapes(n, n):
        multiplicity = {}
        for size in shape:
            multiplicity[size] = multiplicity.get(size, 0) + 1
        denominator = 1
        for size, count in multiplicity.items():
            denominator *= factorial(size) ** count * factorial(count)
        partitions = factorial(n) // denominator
        bijections = 1
        for count in multiplicity.values():
            bijections *= factorial(count)
        total += partitions * partitions * bijections
    return total


def identify_objects(family):
    """Check, case by case, that `dss.w_count` counts subset-sum solutions and not mappings.

    The claim that two quantities count different objects is the load-bearing one in this module: it
    is what licenses refusing the comparison instead of publishing a spurious undercount.  So it is
    checked rather than asserted — against an independent Python re-derivation of `W(E)`, and
    against `|M|` for the cases where the two numbers happen to coincide anyway.
    """
    import dss

    checked = mismatches = coincidences = 0
    examples = []
    for inputs, outputs in family:
        count = dss.w_count(list(inputs), list(outputs))
        if str(count.get("kind", "")).lower() != "exact" or count.get("count") is None:
            continue
        checked += 1
        derived = _subset_sum_solutions(inputs, outputs)
        exact = len(exact_subtransaction_mappings(inputs, outputs))
        if count["count"] != derived:
            mismatches += 1
            if len(examples) < MAX_EXAMPLES:
                examples.append({
                    "inputs": list(inputs), "outputs": list(outputs),
                    "dss_w_count": count["count"], "rederived_subset_sum_solutions": derived,
                })
        if count["count"] == exact:
            coincidences += 1
    return {
        "object": "non-empty proper input subsets whose sum is a proper output-subset sum, W(E)",
        "rederivation": "decluster.baselines.oracle_audit._subset_sum_solutions",
        "exact_answers_checked": checked,
        "rederivation_mismatches": mismatches,
        "rederivation_examples": examples,
        "cases_where_w_equals_exact_mapping_count": coincidences,
        "verdict": (
            "W(E) identified: dss.w_count reproduces the independent subset-sum re-derivation on "
            f"{checked - mismatches}/{checked} exact answers. It is not the mapping count, so this "
            "module reports the object mismatch and refuses to score it as an under/overcount."
        ) if checked and not mismatches else (
            "W(E) NOT identified: the re-derivation disagrees with dss.w_count, so the object "
            "behind that entry point is still unknown and no verdict about it is published here."
        ),
    }


def _dss_mapping_analysis(inputs, outputs):
    import dss

    try:
        return dss.mapping_analysis(list(inputs), list(outputs), None)
    except BaseException:
        return None


def approx_mapping_count(inputs, outputs):
    report = _dss_mapping_analysis(inputs, outputs)
    return None if report is None else report.get("n_non_derived")


def approx_mapping_entropy_bits(inputs, outputs):
    report = _dss_mapping_analysis(inputs, outputs)
    return None if report is None else report.get("entropy")


def approx_link_matrix(inputs, outputs):
    from .. import counting

    return counting.link_matrix(list(inputs), list(outputs))


def approx_deterministic_links(inputs, outputs):
    report = _dss_mapping_analysis(inputs, outputs)
    if report is None:
        return None
    return {(int(i), int(j)) for i, j in report.get("deterministic_links", ())}


def exact_mapping_count(inputs, outputs):
    return len(exact_subtransaction_mappings(inputs, outputs))


def exact_mapping_entropy_bits(inputs, outputs):
    return exact_link_analysis(inputs, outputs).entropy_bits


def exact_link_matrix(inputs, outputs):
    matrix = exact_link_analysis(inputs, outputs).matrix
    return matrix or None


def exact_deterministic_links(inputs, outputs):
    return set(exact_link_analysis(inputs, outputs).deterministic_links)


def finest_mappings(mappings):
    """The mappings no other mapping strictly refines: the refinement order's maximal elements.

    This is what "finest" means on a poset of partitions, and it is the reason to prefer it: a
    mapping belongs here exactly when nothing splits it further, which is the property the word
    names.  It is NOT chosen for being the strongest reading available to the approximation, and an
    earlier draft of this docstring claimed that it was, which is inverted.  Selecting instead by
    *maximum block count* keeps a strict subset of these — a strict refinement always has strictly
    more blocks, so an argmax-by-block-count mapping is always refinement-maximal but not
    conversely — which is a SMALLER oracle family, hence MORE oracle certainties, hence a reading
    strictly more generous to the approximation.  `finest_selection_sensitivity` measures exactly
    what that costs, because the difference is not cosmetic: it is where "no certain link is missed"
    stops holding.
    """
    return non_derived_mappings(mappings)


def max_block_count_mappings(mappings):
    """The mappings with the most blocks — a strict subset of `finest_mappings`.

    Kept only so the audit can measure how much the finest-only cross-check depends on which notion
    of "finest" is used.  Not the notion this module compares against; see `finest_mappings`.
    """
    mappings = tuple(mappings)
    if not mappings:
        return ()
    most = max(len(mapping.blocks) for mapping in mappings)
    return tuple(mapping for mapping in mappings if len(mapping.blocks) == most)


def _certain_links(mappings, input_count, output_count):
    if not mappings:
        return set()
    counts = [[0] * output_count for _ in range(input_count)]
    for mapping in mappings:
        for in_block, out_block in mapping.blocks:
            for i in in_block:
                for j in out_block:
                    counts[i][j] += 1
    return {(i, j) for i, row in enumerate(counts) for j, count in enumerate(row)
            if count == len(mappings)}


def finest_selection_sensitivity(family):
    """How much the finest-only cross-check depends on the definition of "finest".

    The audit compares against the refinement-maximal mappings.  Selecting by maximum block count
    instead keeps a strict subset, so the oracle family shrinks and its certain links multiply, and
    the cross-check's "no certain link is missed" is a statement about the first selection only.
    Measured here on every run rather than described once, because a claim that holds under one
    definition and fails under another must carry the definition with it.
    """
    import dss

    divergent = 0
    tallies = {
        "refinement_maximal": {"spurious_links": 0, "missed_links": 0},
        "max_block_count": {"spurious_links": 0, "missed_links": 0},
    }
    for inputs, outputs in family:
        mappings = exact_subtransaction_mappings(inputs, outputs)
        if not mappings:
            continue
        maximal = finest_mappings(mappings)
        by_blocks = max_block_count_mappings(mappings)
        if {m.blocks for m in maximal} != {m.blocks for m in by_blocks}:
            divergent += 1
        matrix = dss.pairwise_link_prob(list(inputs), list(outputs), None)
        if not matrix:
            continue
        claimed = {(i, j) for i, row in enumerate(matrix)
                   for j, value in enumerate(row) if value == 1.0}
        for key, selection in (("refinement_maximal", maximal), ("max_block_count", by_blocks)):
            certain = _certain_links(selection, len(inputs), len(outputs))
            tallies[key]["spurious_links"] += len(claimed - certain)
            tallies[key]["missed_links"] += len(certain - claimed)
    return {
        "cases": len(family),
        "cases_where_the_two_selections_differ": divergent,
        **tallies,
        "note": (
            "The audit's cross-check uses refinement-maximal selection, the maximal elements of "
            "the refinement order, because that is what 'finest' means on a poset of partitions. "
            "Under "
            "max-block-count selection — a strict subset, so a smaller oracle family and more "
            "oracle certainties, a reading strictly more generous to the approximation — the "
            "spurious count falls and certain links begin to read as missed. The primary "
            "deterministic_links probe uses neither: it runs against the full oracle family."
        ),
    }


def _finest_link_counts(inputs, outputs):
    mappings = finest_mappings(exact_subtransaction_mappings(inputs, outputs))
    if not mappings:
        return None, 0
    counts = [[0] * len(outputs) for _ in inputs]
    for mapping in mappings:
        for in_block, out_block in mapping.blocks:
            for i in in_block:
                for j in out_block:
                    counts[i][j] += 1
    return counts, len(mappings)


def exact_finest_link_matrix(inputs, outputs):
    counts, total = _finest_link_counts(inputs, outputs)
    if not total:
        return None
    return tuple(tuple(count / total for count in row) for row in counts)


def exact_finest_deterministic_links(inputs, outputs):
    counts, total = _finest_link_counts(inputs, outputs)
    if not total:
        return set()
    return {(i, j) for i, row in enumerate(counts) for j, count in enumerate(row)
            if count == total}


def verify_dss_marginal_family(family):
    """Re-derive, rather than assert, that `pairwise_link_prob` marginalizes dss's OWN family.

    Two checks, both one-liners over the returned matrix, and this is what demotes the matrix from
    "the same object as the oracle's marginal" to "the same quantity over a restricted family":
    every entry is an exact multiple of `1 / n_non_derived`, and the entries equal to 1.0 are
    exactly the `deterministic_links` the same call reports.  A marginal, a count and a certain-link
    set out of one enumeration cannot carry three different comparability verdicts.
    """
    import dss

    checked = quantized = links_match = smaller = 0
    counterexamples = []
    for inputs, outputs in family:
        analysis = dss.mapping_analysis(list(inputs), list(outputs), None)
        matrix = dss.pairwise_link_prob(list(inputs), list(outputs), None)
        if analysis is None or not matrix or not analysis.get("n_non_derived"):
            continue
        checked += 1
        total = analysis["n_non_derived"]
        is_quantized = all(abs(value * total - round(value * total)) <= TOLERANCE
                           for row in matrix for value in row)
        ones = {(i, j) for i, row in enumerate(matrix) for j, value in enumerate(row)
                if value == 1.0}
        reported = {(int(i), int(j)) for i, j in analysis.get("deterministic_links", ())}
        quantized += is_quantized
        links_match += (ones == reported)
        if total < exact_mapping_count(inputs, outputs):
            smaller += 1
        if not (is_quantized and ones == reported) and len(counterexamples) < MAX_EXAMPLES:
            counterexamples.append({
                "inputs": list(inputs), "outputs": list(outputs),
                "n_non_derived": total, "matrix": [list(row) for row in matrix],
                "deterministic_links": sorted(reported),
            })
    return {
        "cases_checked": checked,
        "entries_are_multiples_of_one_over_n_non_derived": quantized,
        "unit_entries_equal_the_reported_deterministic_links": links_match,
        "cases_where_the_dss_family_is_strictly_smaller_than_the_oracle_family": smaller,
        "counterexamples": counterexamples,
        "verdict": (
            "pairwise_link_prob is the uniform marginal over dss's own family: quantized to "
            f"1/n_non_derived on {quantized}/{checked} cases and unit-valued exactly on the "
            f"deterministic links it reports on {links_match}/{checked}. That family is strictly "
            f"smaller than the oracle's on {smaller} cases, so the matrix, the count and the "
            "certain-link set are all restrictions and none is a bound in either direction."
        ) if checked and quantized == links_match == checked else (
            "NOT verified: the matrix is not consistent with a uniform marginal over n_non_derived "
            "mappings on every case, so the restriction claim is withheld."
        ),
    }


def mapping_count_mechanism(family):
    """Measure the relation between `n_non_derived` and refinement-maximal mappings."""
    import dss

    equal_to_finest = differs_from_finest = 0
    all_equal_value = all_equal_value_answering_one = 0
    examples = []
    for inputs, outputs in family:
        total = dss.mapping_analysis(list(inputs), list(outputs), None)["n_non_derived"]
        finest = len(finest_mappings(exact_subtransaction_mappings(inputs, outputs)))
        if total == finest:
            equal_to_finest += 1
        else:
            differs_from_finest += 1
            if len(examples) < MAX_EXAMPLES:
                examples.append({
                    "inputs": list(inputs), "outputs": list(outputs),
                    "n_non_derived": total, "finest_oracle_mappings": finest,
                })
        if len(set(inputs + outputs)) == 1:
            all_equal_value += 1
            all_equal_value_answering_one += (total == 1)
    return {
        "cases": len(family),
        "equal_to_the_finest_oracle_mapping_count": equal_to_finest,
        "different_from_the_finest_oracle_mapping_count": differs_from_finest,
        "examples_where_it_differs": examples,
        "all_equal_value_cases": all_equal_value,
        "all_equal_value_cases_answering_one": all_equal_value_answering_one,
        "note": (
            "The current DSS count equals the independent refinement-maximal mapping count on the "
            "entire bounded family. Equal-value permutations do not collapse in general: "
            "`[1,3,4,4] -> [3,3,3,3]` answers 4, and those readings differ only in which "
            "equal-valued output stands alone. Agreement on this family is measured, not universal."
        ),
    }


# name -> (kind, relation, object note, exact side, approximate side). `kind` picks the comparison
# engine; nothing else in this module dispatches on the probe name.
PROBES = {
    "mapping_count": (
        "scalar", RESTRICTION,
        "mappings both sides, over dss's refinement-maximal family against every index-level "
        "balanced set partition",
        exact_mapping_count, approx_mapping_count,
    ),
    "mapping_entropy_bits": (
        "scalar", RESTRICTION,
        "both are log2 of a mapping count under a uniform prior, over the two families named for "
        "mapping_count",
        exact_mapping_entropy_bits, approx_mapping_entropy_bits,
    ),
    "link_matrix": (
        "matrix", RESTRICTION,
        "P(input i and output j share a block): the same quantity both sides, but dss marginalizes "
        "over its own restricted family (verify_dss_marginal_family), so it bounds the oracle's "
        "marginal in neither direction",
        exact_link_matrix, approx_link_matrix,
    ),
    "deterministic_links": (
        "links", RESTRICTION,
        "the (input, output) pairs every mapping agrees on — over dss's family against the "
        "oracle's; counting.link_matrix's docstring reads a unit row to consumers as 'the amounts "
        "settle that assignment on their own', which is the claim a spurious link makes",
        exact_deterministic_links, approx_deterministic_links,
    ),
    # The same two comparisons against the finest-only oracle view, so the finding is visibly
    # independent of the oracle's inclusion of coarser readings.
    "link_matrix_finest_only": (
        "matrix", RESTRICTION,
        "as link_matrix, but the oracle side keeps only the maximal-refinement mappings",
        exact_finest_link_matrix, approx_link_matrix,
    ),
    "deterministic_links_finest_only": (
        "links", RESTRICTION,
        "as deterministic_links, but the oracle side keeps only the maximal-refinement mappings",
        exact_finest_deterministic_links, approx_deterministic_links,
    ),
}


def _bound_direction(under, over, agree):
    if over and under:
        return "neither"
    if over:
        return "upper"
    if under:
        return "lower"
    return "exact" if agree else "unmeasured"


def _note_relative_error(stats, exact, approx):
    relative = _relative_error(exact, approx)
    if relative is None:
        stats["undefined_relative_errors"] += 1
    else:
        stats["max_relative_error"] = max(stats["max_relative_error"], relative)


def _record_example(stats, item):
    """Every exceedance is counted; `MAX_EXAMPLES` of them are carried as worked cases."""
    stats["exceeds_exact_cases"] += 1
    if len(stats["exceeds_exact"]) < MAX_EXAMPLES:
        stats["exceeds_exact"].append(item)


def _relative_error(exact, approx):
    """`None` where it is undefined — an exact zero against a non-zero approximation.

    Reporting that as an infinite maximum would put `Infinity` in the JSON and swallow the finite
    worst case behind it, so undefined entries are counted separately instead.
    """
    if exact:
        return abs(approx - exact) / abs(exact)
    return 0.0 if approx == 0 else None


def _compare_scalar(family, exact_fn, approx_fn, tolerance):
    stats = {
        "compared": 0, "refusals": 0, "agreements": 0, "undercounts": 0, "overcounts": 0,
        "max_absolute_error": 0.0, "max_relative_error": 0.0, "undefined_relative_errors": 0,
        "exceeds_exact_cases": 0, "exceeds_exact": [],
    }
    rows = []
    for inputs, outputs in family:
        exact, approx = exact_fn(inputs, outputs), approx_fn(inputs, outputs)
        row = {"exact": exact, "approx": approx}
        if approx is None:
            stats["refusals"] += 1
            rows.append(row)
            continue
        stats["compared"] += 1
        absolute = abs(approx - exact)
        row["absolute_error"] = absolute
        stats["max_absolute_error"] = max(stats["max_absolute_error"], absolute)
        _note_relative_error(stats, exact, approx)
        if absolute <= tolerance:
            stats["agreements"] += 1
        elif approx < exact:
            stats["undercounts"] += 1
        else:
            stats["overcounts"] += 1
            _record_example(stats, {
                "inputs": list(inputs), "outputs": list(outputs), "exact": exact, "approx": approx,
            })
        rows.append(row)
    stats["bound_direction"] = _bound_direction(
        stats["undercounts"], stats["overcounts"], stats["agreements"])
    return stats, rows


def _compare_matrix(family, exact_fn, approx_fn, tolerance):
    stats = {
        "compared": 0, "refusals": 0, "shape_mismatches": 0, "agreements": 0, "disagreements": 0,
        "entries": 0, "entries_agreeing": 0, "entries_above_exact": 0, "entries_below_exact": 0,
        "max_absolute_error": 0.0, "max_relative_error": 0.0, "undefined_relative_errors": 0,
        "exceeds_exact_cases": 0, "exceeds_exact": [],
    }
    rows = []
    for inputs, outputs in family:
        exact, approx = exact_fn(inputs, outputs), approx_fn(inputs, outputs)
        row = {}
        if exact is None or approx is None:
            stats["refusals"] += 1
            rows.append(row)
            continue
        if len(approx) != len(exact) or any(len(a) != len(e) for a, e in zip(approx, exact)):
            stats["shape_mismatches"] += 1
            rows.append({"shape_mismatch": True})
            continue
        stats["compared"] += 1
        above = below = 0
        worst = 0.0
        for exact_row, approx_row in zip(exact, approx):
            for e, a in zip(exact_row, approx_row):
                stats["entries"] += 1
                delta = a - e
                worst = max(worst, abs(delta))
                _note_relative_error(stats, e, a)
                if abs(delta) <= tolerance:
                    stats["entries_agreeing"] += 1
                elif delta > 0:
                    above += 1
                else:
                    below += 1
        stats["entries_above_exact"] += above
        stats["entries_below_exact"] += below
        stats["max_absolute_error"] = max(stats["max_absolute_error"], worst)
        row.update({"entries_above_exact": above, "entries_below_exact": below,
                    "max_absolute_error": worst})
        if above or below:
            stats["disagreements"] += 1
        else:
            stats["agreements"] += 1
        if above:
            _record_example(stats, {
                "inputs": list(inputs), "outputs": list(outputs),
                "entries_above_exact": above, "max_absolute_error": worst,
            })
        rows.append(row)
    stats["bound_direction"] = _bound_direction(
        stats["entries_below_exact"], stats["entries_above_exact"], stats["entries_agreeing"])
    return stats, rows


def _compare_links(family, exact_fn, approx_fn, tolerance):
    """Set comparison of certain links.

    `spurious` is a link the approximation calls certain that the oracle does not: a manufactured
    de-anonymization, and the only direction of error here that costs a holder privacy they were
    told they had.  `missed` is the opposite — a certainty the oracle finds and the approximation
    does not, which loses an adversary a link rather than inventing one."""
    stats = {
        "compared": 0, "refusals": 0, "agreements": 0, "undercounts": 0, "overcounts": 0,
        "spurious_links": 0, "missed_links": 0, "exceeds_exact_cases": 0, "exceeds_exact": [],
    }
    rows = []
    for inputs, outputs in family:
        exact, approx = exact_fn(inputs, outputs), approx_fn(inputs, outputs)
        if approx is None:
            stats["refusals"] += 1
            rows.append({})
            continue
        stats["compared"] += 1
        spurious, missed = approx - exact, exact - approx
        stats["spurious_links"] += len(spurious)
        stats["missed_links"] += len(missed)
        if not spurious and not missed:
            stats["agreements"] += 1
        elif spurious:
            stats["overcounts"] += 1
            _record_example(stats, {
                "inputs": list(inputs), "outputs": list(outputs),
                "spurious_links": sorted(spurious), "missed_links": sorted(missed),
            })
        else:
            stats["undercounts"] += 1
        rows.append({"exact": len(exact), "approx": len(approx),
                     "spurious": sorted(spurious), "missed": sorted(missed)})
    stats["bound_direction"] = _bound_direction(
        stats["undercounts"], stats["overcounts"], stats["agreements"])
    return stats, rows


_ENGINES = {"scalar": _compare_scalar, "matrix": _compare_matrix, "links": _compare_links}


def _per_coin_density_identification(family):
    """Measure the structural property that makes `per_coin_density` a different reading: whether
    its per-coin `log_w` varies across the coins of one transaction, where the marginals do."""
    import dss

    coin_invariant = varying = refusals = 0
    exact_varying = 0
    for inputs, outputs in family:
        try:
            report = dss.per_coin_density(list(inputs), list(outputs))
        except BaseException:
            refusals += 1
            continue
        values = {c.get("log_w") for c in report.get("coins", ())}
        if not values:
            refusals += 1
            continue
        if len(values) == 1:
            coin_invariant += 1
        else:
            varying += 1
        evidence = exact_per_coin_link_evidence(inputs, outputs)
        if len({c.max_link_probability for c in evidence.inputs}) > 1:
            exact_varying += 1
    return {
        "object": "per-coin log_w (natural log) from the fee-aware density path, not a probability",
        "coin_invariant_cases": coin_invariant,
        "coin_varying_cases": varying,
        "refusals": refusals,
        "cases_where_exact_input_marginals_vary": exact_varying,
        "note": (
            "log_w is a natural log while the oracle's entropy is in bits, and the quantity is a "
            "subset-sum density rather than a link marginal, so no entrywise comparison is made. "
            "The reportable fact is structural: where its value is identical for every coin of a "
            "transaction it cannot express per-coin variation that the exact marginals do show."
        ),
    }


def _radix_identification(family):
    """Two structural facts about `radix_mappings`, each demonstrated rather than argued.

    Input independence: the call takes the outputs and a knee, so one answer stands for every
    transaction sharing an output multiset — and the family contains output multisets whose exact
    mapping count differs across the inputs that fund them.

    Scale dependence: `|M|` is invariant under multiplying every coin by a constant, because the
    balance conditions scale with it.  `radix_mappings` is not, so the pair (unscaled, scaled) is a
    witness that the two cannot be the same quantity — no bound argument needed.
    """
    import dss

    from .. import counting

    by_outputs = {}
    for inputs, outputs in family:
        by_outputs.setdefault(outputs, []).append(inputs)

    applicable = answered = scale_flips = 0
    witnesses, scale_witnesses = [], []
    for outputs, input_sets in sorted(by_outputs.items()):
        if not counting.radix_applies(list(outputs)):
            continue
        applicable += 1
        count = dss.radix_mappings(list(outputs), counting.KNEE).get("count") or 0
        scaled = tuple(value * RADIX_SCALE for value in outputs)
        scaled_count = dss.radix_mappings(list(scaled), counting.KNEE).get("count") or 0
        exacts = {len(exact_subtransaction_mappings(i, outputs)) for i in input_sets}
        if count:
            answered += 1
            if len(exacts) > 1 and len(witnesses) < MAX_EXAMPLES:
                witnesses.append({
                    "outputs": list(outputs), "radix_count": count,
                    "exact_mapping_counts": sorted(exacts),
                })
        if scaled_count != count:
            scale_flips += 1
            scaled_exacts = {
                len(exact_subtransaction_mappings(tuple(v * RADIX_SCALE for v in i), scaled))
                for i in input_sets
            }
            if len(scale_witnesses) < MAX_EXAMPLES:
                scale_witnesses.append({
                    "outputs": list(outputs), "radix_count": count,
                    "scaled_outputs": list(scaled), "scaled_radix_count": scaled_count,
                    "exact_mapping_counts": sorted(exacts),
                    "scaled_exact_mapping_counts": sorted(scaled_exacts),
                })
    return {
        "object": "permutations of repeated output denominations; a function of the outputs alone",
        "output_multisets_where_radix_applies": applicable,
        "output_multisets_where_radix_returned_a_nonzero_count": answered,
        "input_independence_witnesses": witnesses,
        "scale": RADIX_SCALE,
        "output_multisets_whose_radix_count_moved_under_scaling": scale_flips,
        "scale_dependence_witnesses": scale_witnesses,
        "note": (
            "The call does not take the inputs, so one answer stands for every transaction sharing "
            "an output multiset while the exact mapping count differs across them; and the answer "
            "moves when every coin is multiplied by a constant, which the exact mapping count "
            "cannot. A quantity blind to a parameter the target depends on, and sensitive to one "
            "it does not, is not a bound on the target."
        ),
    }


def _subtransaction_identification(family):
    """`subtransaction.subtransactions` on the 2-in/2-out slice: count of positive implied payments,
    with no balance requirement, so compare it only as an identified different object."""
    from .. import subtransaction

    from math import log2

    slice_size = exceeds = agrees = below = refusals = 0
    for inputs, outputs in family:
        if len(inputs) != 2 or len(outputs) != 2:
            continue
        slice_size += 1
        tx = {
            "txid": "audit",
            "vin": [{"txid": f"in{i}", "prevout": {"value": v}} for i, v in enumerate(inputs)],
            "vout": [{"value": v} for v in outputs],
        }
        _, bits = subtransaction.subtransactions(tx)
        if bits is None:
            refusals += 1
            continue
        exact = log2(max(len(exact_subtransaction_mappings(inputs, outputs)), 1))
        if abs(bits - exact) <= TOLERANCE:
            agrees += 1
        elif bits > exact:
            exceeds += 1
        else:
            below += 1
    return {
        "object": "log2 of the number of (receiver input, receiver output) pairs with a positive "
                  "implied payment; no block is required to balance",
        "two_in_two_out_cases": slice_size,
        "refusals": refusals,
        "cases_above_exact_entropy": exceeds,
        "cases_equal_to_exact_entropy": agrees,
        "cases_below_exact_entropy": below,
        "note": (
            "Its own docstring already calls this a count diagnostic and not a privacy quantity. "
            "The count admits partitions that do not conserve value, so it is neither a bound on "
            "nor an estimate of the oracle's mapping entropy; the tallies above describe how the "
            "two numbers happen to order, not a bound."
        ),
    }


def _router_identification(family):
    """`counting.count_w` (the production router) and `counting.saddle_point_log_w`.

    The router's tiers are radix then sparse, and the sparse tier answers the same subset-sum count
    `w_count` does — checked here against the same re-derivation — so the router inherits that
    object mismatch rather than acquiring a new one.  The saddle point is recorded because its own
    gate and the gate `counting.is_dense` reports are not the same gate, and the size of that gap is
    measurable.
    """
    from collections import Counter

    from .. import counting

    methods, kinds = Counter(), Counter()
    sparse_matches_rederivation = sparse_answers = 0
    saddle_answers = dense_by_is_dense = 0
    for inputs, outputs in family:
        routed = counting.count_w(list(inputs), list(outputs))
        methods[routed.get("method")] += 1
        kinds[str(routed.get("kind"))] += 1
        if routed.get("method") == "sparse" and routed.get("count") is not None:
            sparse_answers += 1
            sparse_matches_rederivation += (
                routed["count"] == _subset_sum_solutions(inputs, outputs))
        saddle_answers += counting.saddle_point_log_w(list(inputs), list(outputs)) is not None
        dense_by_is_dense += bool(counting.is_dense(list(inputs), list(outputs)))
    return {
        "object": "count_w routes to radix or sparse; the sparse answer is the same subset-sum "
                  "solution count W(E), so the router is a different object from |M| for the same "
                  "reason w_count is",
        "methods": dict(methods),
        "kinds": dict(kinds),
        "sparse_answers": sparse_answers,
        "sparse_answers_matching_the_subset_sum_rederivation": sparse_matches_rederivation,
        "saddle_point_answers": saddle_answers,
        "cases_is_dense_reads_as_dense": dense_by_is_dense,
        "note": (
            "The radix tier never wins on this family: it returns zero, `_resolved` reads that as "
            "no answer, and the route falls through to sparse. The saddle point declines every "
            "case here even though `is_dense` reads most of them as Dense, which is the "
            "optimistic-gate discrepancy its own docstring predicts, now measured."
        ),
    }


def audit(family=None, *, tolerance=TOLERANCE, approximations=None, include_cases=True):
    """Compare every like-for-like approximation against the exact oracle and report disagreements.

    `approximations` overrides individual probe providers by name, which is what makes this
    falsifiable: an audit that cannot be made to fail is not an audit, so
    `tests/test_oracle_audit.py` feeds it deliberately wrong counters and asserts the report flags
    them.

    Returns a JSON-serializable report: `comparisons` (the same quantity both sides, each with a
    measured `bound_direction`), `identifications` (the entry points that count a different object,
    each with the evidence for that claim), `restriction_evidence` (the re-derivations behind the
    `restriction` verdict itself), `cases` (per-case detail), and `flags` (one line per disagreement
    an approximation would have to answer for before being described as a bound).
    """
    family = list(enumerate_family()) if family is None else list(family)
    overrides = dict(approximations or {})

    comparisons, per_case = {}, {}
    for name, (kind, relation, note, exact_fn, approx_fn) in PROBES.items():
        stats, rows = _ENGINES[kind](family, exact_fn, overrides.get(name, approx_fn), tolerance)
        comparisons[name] = dict(stats, relation=relation, object_note=note, cases=len(family))
        per_case[name] = rows

    identifications = {
        "w_count": identify_objects(family),
        "count_w_router_and_saddle_point": _router_identification(family),
        "radix_mappings": _radix_identification(family),
        "per_coin_density": _per_coin_density_identification(family),
        "subtransaction_ambiguity_bits": _subtransaction_identification(family),
    }
    for identification in identifications.values():
        identification["relation"] = DIFFERENT_OBJECT

    restriction_evidence = {
        "dss_marginal_family": verify_dss_marginal_family(family),
        "mapping_count_mechanism": mapping_count_mechanism(family),
        "finest_selection_sensitivity": finest_selection_sensitivity(family),
    }

    flags = []
    for name, stats in comparisons.items():
        if stats.get("exceeds_exact_cases"):
            flags.append(
                f"{name}: {stats['exceeds_exact_cases']} case(s) where the approximation exceeds "
                f"the exact oracle")
        if stats.get("bound_direction") == "neither":
            flags.append(f"{name}: neither a lower nor an upper bound — errs in both directions")
        if stats.get("spurious_links"):
            flags.append(
                f"{name}: {stats['spurious_links']} link(s) reported as certain that the exact "
                f"oracle leaves ambiguous")
        if stats.get("shape_mismatches"):
            flags.append(f"{name}: {stats['shape_mismatches']} shape mismatch(es)")

    report = {
        "family": {
            "size": len(family),
            "alphabet": list(FAMILY_ALPHABET),
            "max_coins": FAMILY_MAX_COINS,
            "min_side": FAMILY_MIN_SIDE,
            "fee": 0,
            "canonical_form": "sorted input multiset, sorted output multiset; scale not folded",
        },
        "tolerance": tolerance,
        "comparisons": comparisons,
        "identifications": identifications,
        "restriction_evidence": restriction_evidence,
        "flags": flags,
    }
    if include_cases:
        report["cases"] = [
            dict({"inputs": list(inputs), "outputs": list(outputs)},
                 **{name: per_case[name][index] for name in PROBES})
            for index, (inputs, outputs) in enumerate(family)
        ]
    return report


def manifest_invariants(report):
    """The population facts behind the results document, for `reproducibility.write_manifest`.

    A source digest cannot see any of these: the family is generated rather than read, and the
    numbers come out of the Rust crate, whose identity the policy asks for and which
    `fingerprint_source` has no way to record.  Both the writer (`examples/exact_oracle_audit.py
    --manifest`) and the test recompute this from a fresh audit, so a drifting number fails loudly
    instead of standing in the document.
    """
    import dss

    comparisons, identifications = report["comparisons"], report["identifications"]
    return {
        "dss_version": dss.__version__,
        "dss_rev": dss.__rev__,
        "family_size": report["family"]["size"],
        "link_matrix_entries": comparisons["link_matrix"]["entries"],
        "link_matrix_entries_above_exact": comparisons["link_matrix"]["entries_above_exact"],
        "link_matrix_entries_below_exact": comparisons["link_matrix"]["entries_below_exact"],
        "link_matrix_bound_direction": comparisons["link_matrix"]["bound_direction"],
        "spurious_deterministic_links": comparisons["deterministic_links"]["spurious_links"],
        "missed_deterministic_links": comparisons["deterministic_links"]["missed_links"],
        "mapping_count_undercounts": comparisons["mapping_count"]["undercounts"],
        "mapping_count_overcounts": comparisons["mapping_count"]["overcounts"],
        "w_count_rederivation_mismatches": identifications["w_count"]["rederivation_mismatches"],
        "finest_only_entries_above_exact":
            comparisons["link_matrix_finest_only"]["entries_above_exact"],
        "finest_only_entries_below_exact":
            comparisons["link_matrix_finest_only"]["entries_below_exact"],
        "finest_only_spurious_deterministic_links":
            comparisons["deterministic_links_finest_only"]["spurious_links"],
        "finest_only_missed_deterministic_links":
            comparisons["deterministic_links_finest_only"]["missed_links"],
        # Both halves of the document's "507/507", plus the denominator: pinning only the
        # quantization half left the other half of the same claim unchecked.
        "dss_marginal_cases_checked":
            report["restriction_evidence"]["dss_marginal_family"]["cases_checked"],
        "dss_marginal_quantized_cases":
            report["restriction_evidence"]["dss_marginal_family"][
                "entries_are_multiples_of_one_over_n_non_derived"],
        "dss_marginal_unit_entries_match_deterministic_links":
            report["restriction_evidence"]["dss_marginal_family"][
                "unit_entries_equal_the_reported_deterministic_links"],
        "finest_selection_divergent_cases":
            report["restriction_evidence"]["finest_selection_sensitivity"][
                "cases_where_the_two_selections_differ"],
        "max_block_count_spurious_deterministic_links":
            report["restriction_evidence"]["finest_selection_sensitivity"][
                "max_block_count"]["spurious_links"],
        "max_block_count_missed_deterministic_links":
            report["restriction_evidence"]["finest_selection_sensitivity"][
                "max_block_count"]["missed_links"],
        "dss_family_strictly_smaller_cases":
            report["restriction_evidence"]["dss_marginal_family"][
                "cases_where_the_dss_family_is_strictly_smaller_than_the_oracle_family"],
    }
