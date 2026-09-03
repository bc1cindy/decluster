import math

import pytest

from decluster.baselines.boltzmann import (
    exact_link_analysis,
    exact_per_coin_link_evidence,
    fee_tolerant_link_analysis,
    fee_tolerant_subtransaction_mappings,
    link_analysis,
)
from decluster.baselines.maurer import exact_subtransaction_mappings


def test_maurer_exact_unique_batch_and_single_owner_readings():
    # Besides the all-coins reading, the only balanced split is
    # (100 -> 100) and (200 -> 200).
    mappings = exact_subtransaction_mappings([100, 200], [100, 200])
    assert len(mappings) == 2
    assert any(len(mapping.blocks) == 1 for mapping in mappings)
    assert any(mapping.blocks == (((0,), (0,)), ((1,), (1,))) for mapping in mappings)


def test_maurer_exact_underdetermined_values_have_three_splits():
    # The 700 output can be funded by 300+400, 200+500, or 100+200+400;
    # the remaining inputs fund 800.  Add the single-owner interpretation.
    mappings = exact_subtransaction_mappings(
        [100, 200, 300, 400, 500], [700, 800]
    )
    assert len(mappings) == 4
    assert sorted(len(mapping.blocks) for mapping in mappings) == [1, 2, 2, 2]


def test_maurer_exact_refuses_fees_instead_of_silently_balancing_them():
    assert exact_subtransaction_mappings([500, 500], [600, 390]) == ()


def test_fee_tolerant_balance_is_separate_and_bounded():
    assert fee_tolerant_subtransaction_mappings(
        [500, 500], [600, 390], fee_tolerance=9
    ) == ()
    mappings = fee_tolerant_subtransaction_mappings(
        [500, 500], [600, 390], fee_tolerance=10
    )
    assert len(mappings) == 1
    assert len(mappings[0].blocks) == 1


def test_fee_can_be_allocated_across_separate_blocks():
    mappings = fee_tolerant_subtransaction_mappings(
        [500, 500], [490, 490], fee_tolerance=20
    )
    assert len(mappings) == 3  # all-coins plus the two indexed pairings


def test_balance_model_is_explicit_in_the_link_result():
    exact = exact_link_analysis([500, 500], [600, 390])
    tolerant = fee_tolerant_link_analysis([500, 500], [600, 390], fee_tolerance=10)
    assert exact.balance_model == "exact" and exact.mappings == ()
    assert tolerant.balance_model == "fee_tolerant" and tolerant.observed_fee == 10
    assert tolerant.fee_tolerance == 10 and len(tolerant.mappings) == 1


def test_roundness_is_not_silently_used_as_a_balance_prior():
    a = fee_tolerant_link_analysis([500, 500], [600, 390], fee_tolerance=10)
    b = fee_tolerant_link_analysis([500, 500], [601, 389], fee_tolerance=10)
    assert a.matrix == b.matrix


@pytest.mark.parametrize("model,tolerance", [("unknown", 0), ("exact", 1)])
def test_invalid_balance_contracts_are_refused(model, tolerance):
    with pytest.raises(ValueError):
        link_analysis([1], [1], balance_model=model, fee_tolerance=tolerance)


def test_boltzmann_exact_matrix_is_derived_from_uniform_mappings():
    analysis = exact_link_analysis([100, 200], [100, 200])
    assert analysis.entropy_bits == pytest.approx(1.0)
    assert analysis.matrix == ((1.0, 0.5), (0.5, 1.0))
    assert analysis.deterministic_links == ((0, 0), (1, 1))


def test_boltzmann_exact_entropy_is_log_of_distinct_readings():
    analysis = exact_link_analysis([100, 200, 300, 400, 500], [700, 800])
    assert analysis.entropy_bits == pytest.approx(math.log2(4))
    assert len(analysis.mappings) == 4
    assert all(0.0 <= probability <= 1.0
               for row in analysis.matrix for probability in row)


def test_reference_baselines_have_an_explicit_exactness_bound():
    with pytest.raises(ValueError, match="max_coins"):
        exact_subtransaction_mappings([1] * 7, [1] * 6)


def test_per_coin_evidence_preserves_exact_mapping_support():
    evidence = exact_per_coin_link_evidence([100, 200], [100, 200])

    assert evidence.mapping_count == 2
    first_input = evidence.inputs[0]
    assert first_input.role == "input"
    assert first_input.candidate_count == 2
    assert first_input.max_link_probability == 1.0
    assert [
        (candidate.counterpart_index, candidate.mapping_count, candidate.probability)
        for candidate in first_input.candidates
    ] == [(0, 2, 1.0), (1, 1, 0.5)]

    first_output = evidence.outputs[0]
    assert first_output.role == "output"
    assert [
        (candidate.counterpart_index, candidate.mapping_count, candidate.probability)
        for candidate in first_output.candidates
    ] == [(0, 2, 1.0), (1, 1, 0.5)]


def test_per_coin_evidence_does_not_hide_an_absent_exact_mapping():
    evidence = exact_per_coin_link_evidence([500, 500], [600, 390])

    assert evidence.mapping_count == 0
    assert all(coin.candidate_count == 0 for coin in evidence.inputs + evidence.outputs)
    assert all(coin.max_link_probability is None for coin in evidence.inputs + evidence.outputs)


def test_per_coin_candidate_counts_are_matrix_support_not_a_privacy_score():
    evidence = exact_per_coin_link_evidence(
        [100, 200, 300, 400, 500], [700, 800]
    )

    assert evidence.mapping_count == 4
    assert [coin.candidate_count for coin in evidence.inputs] == [2, 2, 2, 2, 2]
    assert [coin.candidate_count for coin in evidence.outputs] == [5, 5]
    assert all(coin.max_link_probability == 0.75 for coin in evidence.inputs)
