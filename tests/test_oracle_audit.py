"""The audit of the approximations against the exact oracle, and the audit's own falsifiability.

An audit that cannot fail is decoration. Half of what follows feeds `audit` deliberately wrong
counters — one that overcounts by exactly one, one that undercounts, one that errs in both
directions, a matrix of ones, a link set naming every pair as certain — and asserts the report flags
each. The other half is the measurement itself, on a reduced family so the suite stays fast.
"""
import json
import os
from math import log2

import pytest

from decluster.baselines import exact_link_analysis, exact_subtransaction_mappings
from decluster.baselines import oracle_audit as oa
from decluster.experiments import exact_oracle_audit as experiment

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = "RESULTS-exact-oracle-audit.md"

REDUCED_MAX_COINS = 6


@pytest.fixture(scope="module")
def reduced():
    return oa.enumerate_family(max_coins=REDUCED_MAX_COINS)


@pytest.fixture(scope="module")
def report(reduced):
    pytest.importorskip("dss")
    return oa.audit(reduced, include_cases=False)


def test_family_is_deterministic_exhaustive_and_balanced(reduced):
    assert reduced == oa.enumerate_family(max_coins=REDUCED_MAX_COINS)
    assert len(reduced) == len(set(reduced))
    assert reduced
    for inputs, outputs in reduced:
        assert sum(inputs) == sum(outputs)
        assert len(inputs) >= 2 and len(outputs) >= 2
        assert len(inputs) + len(outputs) <= REDUCED_MAX_COINS
        assert list(inputs) == sorted(inputs) and list(outputs) == sorted(outputs)


def test_equal_value_closed_form_matches_the_oracle():
    # The self-derived form in the module docstring, checked against the enumeration rather than
    # trusted: 3, 16, 131, 1496 for n = 2..5.
    assert [oa.equal_value_mapping_count(n) for n in range(2, 6)] == [3, 16, 131, 1496]
    for n in range(2, 6):
        assert oa.equal_value_mapping_count(n) == len(
            exact_subtransaction_mappings((1,) * n, (1,) * n))


def test_canonical_equal_value_join_has_three_mappings_and_log2_three_bits():
    analysis = exact_link_analysis((5, 5), (5, 5))
    assert len(analysis.mappings) == oa.equal_value_mapping_count(2) == 3
    assert analysis.entropy_bits == pytest.approx(log2(3))
    assert analysis.deterministic_links == ()          # equal values pin nothing


def test_w_count_is_identified_as_subset_sum_solutions_not_mappings(reduced):
    pytest.importorskip("dss")
    identification = oa.identify_objects(reduced)
    assert identification["exact_answers_checked"] > 0
    assert identification["rederivation_mismatches"] == 0
    assert identification["verdict"].startswith("W(E) identified")
    # The re-derivation is of a different object, so it must not coincide with |M| everywhere.
    assert identification["cases_where_w_equals_exact_mapping_count"] < len(reduced)


def test_subset_sum_solutions_rederivation_is_not_the_mapping_count():
    # (1,1,1)/(1,1,1): two proper input subsets sizes {1,2} hitting proper output sums {1,2} gives
    # 3 + 3 = 6 subset-sum solutions, against 16 balanced mappings.
    assert oa._subset_sum_solutions((1, 1, 1), (1, 1, 1)) == 6
    assert len(exact_subtransaction_mappings((1, 1, 1), (1, 1, 1))) == 16


def test_link_matrix_is_neither_a_lower_nor_an_upper_bound(report):
    stats = report["comparisons"]["link_matrix"]
    assert stats["relation"] == oa.RESTRICTION
    assert stats["entries_above_exact"] > 0 and stats["entries_below_exact"] > 0
    assert stats["bound_direction"] == "neither"
    assert stats["exceeds_exact_cases"] > 0
    assert any("neither a lower nor an upper bound" in flag for flag in report["flags"])


def test_the_finding_survives_the_finest_only_reading_of_the_oracle(report):
    """The oracle includes coarser readings up to the single all-coins block. Dropping them —
    refinement-maximal selection — is a robustness reading, NOT the strongest one available to an
    approximation that reports few mappings: max-block-count selection keeps a strict subset, so it
    is smaller, has more oracle certainties and is more generous still (see
    `test_the_finest_only_reading_depends_on_which_notion_of_finest`). Under this reading the
    verdict does not move: still both directions, still the same certain-link overclaim."""
    stats = report["comparisons"]["link_matrix_finest_only"]
    assert stats["entries_above_exact"] > 0 and stats["entries_below_exact"] > 0
    assert stats["bound_direction"] == "neither"
    links = report["comparisons"]["deterministic_links_finest_only"]
    assert links["missed_links"] == 0
    assert links["spurious_links"] == report["comparisons"]["deterministic_links"]["spurious_links"]


def test_the_finest_only_reading_depends_on_which_notion_of_finest():
    """The cross-check's "no certain link missed" holds under refinement-maximal selection and NOT
    under max-block-count selection, which keeps a strict subset. The audit measures both rather
    than describing the choice once, because a claim that turns on a definition must carry it.

    The 132-case reduced family is too small to separate them — the two selections already differ
    there, but not yet on a case that costs a certain link — so this one runs at max_coins=7 (270
    cases, ~0.2 s), the smallest family where the divergence reaches the tally.
    """
    pytest.importorskip("dss")
    sensitivity = oa.finest_selection_sensitivity(oa.enumerate_family(max_coins=7))
    assert sensitivity["cases_where_the_two_selections_differ"] == 32     # oracle-only, no dss
    assert sensitivity["refinement_maximal"]["missed_links"] == 0
    assert sensitivity["max_block_count"]["missed_links"] > 0
    # Strictly more generous to the approximation: fewer spurious, because more oracle certainties.
    assert (sensitivity["max_block_count"]["spurious_links"]
            < sensitivity["refinement_maximal"]["spurious_links"])


def test_max_block_count_selection_is_a_strict_subset_of_the_refinement_maximal_one(reduced):
    """A strict refinement always has strictly more blocks, so argmax-by-block-count is always
    refinement-maximal — the containment that makes it the smaller, more generous oracle family."""
    strictly_smaller = 0
    for inputs, outputs in reduced:
        mappings = exact_subtransaction_mappings(inputs, outputs)
        maximal = {m.blocks for m in oa.finest_mappings(mappings)}
        by_blocks = {m.blocks for m in oa.max_block_count_mappings(mappings)}
        assert by_blocks <= maximal
        strictly_smaller += by_blocks < maximal
    assert strictly_smaller > 0


def test_finest_mappings_keeps_only_the_maximal_refinements():
    mappings = exact_subtransaction_mappings((2, 2), (1, 1, 2))
    finest = oa.finest_mappings(mappings)
    assert len(mappings) == 3 and len(finest) == 2
    assert all(len(m.blocks) == 2 for m in finest)          # the single-block reading is dropped
    # An unambiguous transaction keeps its one mapping rather than losing it.
    assert len(oa.finest_mappings(exact_subtransaction_mappings((1, 3), (2, 2)))) == 1


def test_dss_marginal_is_verified_to_be_over_dss_own_family(reduced):
    """The one-line check that demotes the matrix from "same object" to "restriction": if it were
    the oracle's marginal it would not be quantized to dss's own mapping count."""
    pytest.importorskip("dss")
    evidence = oa.verify_dss_marginal_family(reduced)
    checked = evidence["cases_checked"]
    assert checked == len(reduced)
    assert evidence["entries_are_multiples_of_one_over_n_non_derived"] == checked
    assert evidence["unit_entries_equal_the_reported_deterministic_links"] == checked
    assert evidence["counterexamples"] == []
    assert 0 < evidence[
        "cases_where_the_dss_family_is_strictly_smaller_than_the_oracle_family"] <= checked
    assert evidence["verdict"].startswith("pairwise_link_prob is the uniform marginal")


def test_mapping_analysis_pairwise_matrix_and_exact_oracle_are_cross_checked(reduced):
    """Exercise the public DSS diagnostics and the independent oracle in one differential test."""
    pytest.importorskip("dss")
    import dss

    saw_above = saw_below = False
    for inputs, outputs in reduced:
        diagnostics = dss.mapping_analysis(list(inputs), list(outputs), None)
        assert diagnostics["status"] == "complete"
        matrix = dss.pairwise_link_prob(list(inputs), list(outputs), None)
        claimed = {(i, o) for i, row in enumerate(matrix)
                   for o, probability in enumerate(row) if probability == 1.0}
        assert claimed == {tuple(link) for link in diagnostics["deterministic_links"]}

        exact = exact_link_analysis(inputs, outputs).matrix
        for approximate_row, exact_row in zip(matrix, exact):
            for approximate, reference in zip(approximate_row, exact_row):
                saw_above |= approximate > reference + oa.TOLERANCE
                saw_below |= approximate < reference - oa.TOLERANCE

    assert saw_above and saw_below


def test_mapping_count_matches_refinement_maximal_family_without_collapsing_indices(reduced):
    pytest.importorskip("dss")
    import dss

    mechanism = oa.mapping_count_mechanism(reduced)
    assert mechanism["equal_to_the_finest_oracle_mapping_count"] == len(reduced)
    assert mechanism["different_from_the_finest_oracle_mapping_count"] == 0
    assert mechanism["all_equal_value_cases"] > 0
    assert mechanism["all_equal_value_cases_answering_one"] == 0
    # Two refinement-maximal mappings survive.
    assert dss.mapping_analysis([2, 2], [1, 1, 2], None)["n_non_derived"] == 2
    assert len(oa.finest_mappings(exact_subtransaction_mappings((2, 2), (1, 1, 2)))) == 2
    # Equal-value permutations do not collapse in general.
    assert dss.mapping_analysis([1, 3, 4, 4], [3, 3, 3, 3], None)["n_non_derived"] == 4


def test_the_router_and_the_saddle_point_are_probed(report):
    identification = report["identifications"]["count_w_router_and_saddle_point"]
    assert identification["relation"] == oa.DIFFERENT_OBJECT
    assert identification["sparse_answers"] > 0
    assert (identification["sparse_answers_matching_the_subset_sum_rederivation"]
            == identification["sparse_answers"])
    assert identification["methods"].get("radix") is None      # the radix tier never wins here
    assert identification["saddle_point_answers"] == 0
    assert identification["cases_is_dense_reads_as_dense"] > 0


def test_deterministic_links_are_overclaimed_and_never_missed(report):
    stats = report["comparisons"]["deterministic_links"]
    assert stats["spurious_links"] > 0
    assert stats["missed_links"] == 0
    assert stats["bound_direction"] == "upper"


def test_mapping_count_undercounts_across_this_family_and_never_exceeds(report):
    stats = report["comparisons"]["mapping_count"]
    assert stats["relation"] == oa.RESTRICTION
    assert stats["undercounts"] > 0
    assert stats["overcounts"] == 0 and stats["exceeds_exact_cases"] == 0
    assert stats["bound_direction"] == "lower"


def test_radix_is_identified_as_input_blind_and_scale_dependent(report):
    identification = report["identifications"]["radix_mappings"]
    assert identification["relation"] == oa.DIFFERENT_OBJECT
    assert identification["output_multisets_where_radix_applies"] > 0
    assert identification["output_multisets_whose_radix_count_moved_under_scaling"] > 0
    for witness in identification["scale_dependence_witnesses"]:
        assert witness["exact_mapping_counts"] == witness["scaled_exact_mapping_counts"]
        assert witness["radix_count"] != witness["scaled_radix_count"]


def test_per_coin_density_is_coin_invariant_where_the_exact_marginals_vary(report):
    identification = report["identifications"]["per_coin_density"]
    assert identification["coin_invariant_cases"] > 0
    assert identification["cases_where_exact_input_marginals_vary"] > 0


def test_report_is_strictly_json_serializable_with_cases(reduced):
    pytest.importorskip("dss")
    full = oa.audit(reduced[:20])
    assert len(full["cases"]) == 20
    # allow_nan=False: an undefined relative error must be counted, never emitted as Infinity.
    assert json.loads(json.dumps(full, allow_nan=False))["family"]["fee"] == 0
    assert oa._relative_error(0, 1) is None and oa._relative_error(0, 0) == 0.0


def _flags(report, name):
    return [flag for flag in report["flags"] if flag.startswith(name + ":")]


def test_audit_detects_a_counter_that_overcounts_by_one(reduced):
    """The detection test the deliverable turns on: an approximation off by +1 must be flagged as
    exceeding the oracle, on every case, with the offending cases named."""
    report = oa.audit(
        reduced, include_cases=False,
        approximations={"mapping_count": lambda i, o: oa.exact_mapping_count(i, o) + 1})
    stats = report["comparisons"]["mapping_count"]
    assert stats["overcounts"] == len(reduced)
    assert stats["undercounts"] == 0 and stats["agreements"] == 0
    assert stats["exceeds_exact_cases"] == len(reduced)
    assert stats["max_absolute_error"] == 1
    assert stats["bound_direction"] == "upper"
    assert stats["exceeds_exact"] and stats["exceeds_exact"][0]["approx"] == (
        stats["exceeds_exact"][0]["exact"] + 1)
    assert _flags(report, "mapping_count")


def test_audit_detects_a_counter_that_undercounts(reduced):
    report = oa.audit(reduced, include_cases=False,
                      approximations={"mapping_count": lambda i, o: 0})
    stats = report["comparisons"]["mapping_count"]
    assert stats["undercounts"] == len(reduced)
    assert stats["overcounts"] == 0 and stats["exceeds_exact_cases"] == 0
    assert stats["bound_direction"] == "lower"
    assert stats["max_relative_error"] == pytest.approx(1.0)


def test_audit_detects_a_counter_that_errs_in_both_directions(reduced):
    def two_faced(inputs, outputs):
        exact = oa.exact_mapping_count(inputs, outputs)
        return exact + 1 if sum(inputs) % 2 else max(exact - 1, 0)

    report = oa.audit(reduced, include_cases=False,
                      approximations={"mapping_count": two_faced})
    stats = report["comparisons"]["mapping_count"]
    assert stats["overcounts"] > 0 and stats["undercounts"] > 0
    assert stats["bound_direction"] == "neither"
    assert any("neither a lower nor an upper bound" in flag
               for flag in _flags(report, "mapping_count"))


def test_audit_detects_a_matrix_of_ones_and_a_shape_mismatch(reduced):
    report = oa.audit(
        reduced, include_cases=False,
        approximations={"link_matrix": lambda i, o: [[1.0] * len(o) for _ in i]})
    stats = report["comparisons"]["link_matrix"]
    assert stats["entries_above_exact"] > 0
    assert stats["entries_below_exact"] == 0
    assert stats["exceeds_exact_cases"] > 0
    assert _flags(report, "link_matrix")

    misshapen = oa.audit(reduced, include_cases=False,
                         approximations={"link_matrix": lambda i, o: [[1.0]]})
    assert misshapen["comparisons"]["link_matrix"]["shape_mismatches"] > 0
    assert any("shape mismatch" in flag for flag in _flags(misshapen, "link_matrix"))


def test_audit_detects_link_sets_that_claim_certainty_everywhere(reduced):
    report = oa.audit(
        reduced, include_cases=False,
        approximations={"deterministic_links":
                        lambda i, o: {(a, b) for a in range(len(i)) for b in range(len(o))}})
    stats = report["comparisons"]["deterministic_links"]
    assert stats["spurious_links"] > 0
    assert stats["exceeds_exact_cases"] > 0
    assert any("reported as certain" in flag for flag in _flags(report, "deterministic_links"))


def test_audit_records_a_refusal_rather_than_scoring_it(reduced):
    report = oa.audit(reduced, include_cases=False,
                      approximations={"mapping_count": lambda i, o: None})
    stats = report["comparisons"]["mapping_count"]
    assert stats["refusals"] == len(reduced)
    assert stats["compared"] == 0
    assert stats["bound_direction"] == "unmeasured"


def test_an_agreeing_approximation_raises_no_flag(reduced):
    report = oa.audit(reduced, include_cases=False,
                      approximations={"mapping_count": oa.exact_mapping_count})
    stats = report["comparisons"]["mapping_count"]
    assert stats["agreements"] == len(reduced)
    assert stats["bound_direction"] == "exact"
    assert not _flags(report, "mapping_count")


def test_published_numbers_are_reproducible_and_the_manifest_is_current():
    """Recompute the canonical artifact and its generated Markdown, without parsing prose."""
    pytest.importorskip("dss")
    artifact_path = os.path.join(ROOT, "results", "artifacts", "exact-oracle-audit-v1.json")
    markdown_path = os.path.join(ROOT, "results", "generated", "exact-oracle-audit-v1.md")
    artifact = experiment.verify_artifact(experiment.load_artifact(artifact_path))
    with open(markdown_path) as generated:
        assert generated.read() == experiment.render_markdown(artifact)

    text = open(os.path.join(ROOT, "results", DOC)).read()
    assert "ground truth" not in text.lower()
    assert "catalog/runs/exact-oracle-audit-v1.json" in text
    policy = open(os.path.join(ROOT, "results", "REPRODUCIBILITY.md")).read()
    assert DOC[:-3] in policy, f"{DOC} is not indexed in REPRODUCIBILITY.md"
