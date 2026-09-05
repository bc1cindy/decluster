import pytest

from decluster.baselines.coinjoin_sudoku import (
    collapse_fee_permutations,
    equal_sum_groupings,
    maximally_separated_groupings,
    uniform_link_probabilities,
)


def test_advisory_valid_and_invalid_group_examples():
    assert len(equal_sum_groupings((2, 3), (1, 4))) == 1
    assert equal_sum_groupings((2, 3), (1, 2)) == ()


def test_sx_control_reconstructs_one_third_relations():
    inputs = (1_010_000,) * 3
    outputs = (1_000_000,) * 3
    mappings = maximally_separated_groupings(inputs, outputs, fee_unit=10_000)
    assert len(mappings) == 36
    assert len(collapse_fee_permutations(mappings, len(outputs))) == 6
    expected = tuple(tuple(pytest.approx(1 / 3) for _ in range(3)) for _ in range(3))
    assert uniform_link_probabilities(inputs, outputs, fee_unit=10_000) == expected


def test_duplicate_values_remain_distinct_indexed_coins():
    assert len(equal_sum_groupings((2, 2), (2, 2))) == 3
    assert len(maximally_separated_groupings((2, 2), (2, 2))) == 2
    assert uniform_link_probabilities((2, 2), (2, 2)) == ((0.5, 0.5), (0.5, 0.5))


def test_fee_requires_an_explicit_exact_unit_convention():
    assert equal_sum_groupings((101,), (100,)) == ()
    assert len(equal_sum_groupings((101,), (100,), fee_unit=1)) == 1
    assert equal_sum_groupings((102,), (100,), fee_unit=3) == ()


@pytest.mark.parametrize("values", [((0,), (0,)), ((-1,), (1,)), ((True,), (1,))])
def test_amount_domain_is_strict(values):
    with pytest.raises(ValueError, match="positive integers"):
        equal_sum_groupings(*values)


def test_bound_is_explicit():
    with pytest.raises(ValueError, match="max_coins"):
        equal_sum_groupings((1,) * 7, (1,) * 7)


def test_fee_expansion_is_bounded_before_materialization():
    with pytest.raises(ValueError, match="max_coins"):
        equal_sum_groupings((10**18,), (1,), fee_unit=1)


@pytest.mark.parametrize("max_coins", [True, 1, 2.5])
def test_invalid_bound_is_rejected(max_coins):
    with pytest.raises(ValueError, match="max_coins"):
        equal_sum_groupings((1,), (1,), max_coins=max_coins)


def test_grouping_count_is_scale_invariant():
    original = equal_sum_groupings((1, 2, 3), (2, 4))
    scaled = equal_sum_groupings((10, 20, 30), (20, 40))
    assert len(original) == len(scaled)


def test_permuting_values_only_relabels_the_uniform_matrix():
    inputs = (2, 3, 5)
    outputs = (3, 7)
    original = uniform_link_probabilities(inputs, outputs)
    permuted = uniform_link_probabilities(inputs[::-1], outputs[::-1])
    assert permuted == tuple(tuple(reversed(row)) for row in reversed(original))
