"""Parity probes transcribed from Samourai-Wallet/boltzmann's official tests.

Expected values were recomputed with commit ed0b649c6ca4abf0cecb69467de6c4e97e847904 and
``options=[LINKABILITY]``. The reference matrix is transposed here to local input-by-output order.
"""

import pytest

from decluster.baselines.boltzmann import fee_tolerant_link_analysis
from decluster.baselines.boltzmann_reference import (
    boltzmann_reference_analysis,
    boltzmann_reference_with_linked_inputs,
)


def _local_counts(inputs, outputs):
    fee = sum(inputs) - sum(outputs)
    analysis = fee_tolerant_link_analysis(inputs, outputs, fee_tolerance=fee)
    total = len(analysis.mappings)
    return total, tuple(tuple(round(probability * total) for probability in row)
                        for row in analysis.matrix)


def test_no_fee_official_vectors_match_boltzmann_count_and_matrix():
    vectors = [
        ((10, 10), (8, 2, 3, 7), 3, ((2, 2, 2, 2), (2, 2, 2, 2))),
        ((10, 10), (8, 2, 2, 8), 5, ((3, 3, 3, 3), (3, 3, 3, 3))),
        ((10, 10), (5, 5, 5, 5), 7, ((4, 4, 4, 4), (4, 4, 4, 4))),
        ((5, 5), (5, 5), 3, ((2, 2), (2, 2))),
        ((5, 5, 5), (5, 5, 5), 16, ((8, 8, 8), (8, 8, 8), (8, 8, 8))),
    ]
    for inputs, outputs, expected_count, expected_matrix in vectors:
        assert _local_counts(inputs, outputs) == (expected_count, expected_matrix)


def test_fee_vector_reproduces_boltzmann_multiplicity_separately():
    # Official TEST P3 with fees reports 28 combinations and each input linked
    # 14/13/13 times to outputs 5/3/2. The local unique-mapping family has 19;
    # Boltzmann's traversal assigns multiplicity to fee-compatible readings.
    count, matrix = _local_counts((5, 5, 5), (5, 3, 2))
    assert (count, matrix) == (19, ((10, 9, 9), (10, 9, 9), (10, 9, 9)))
    assert count != 28
    assert matrix != ((14, 13, 13),) * 3
    reference = boltzmann_reference_analysis((5, 5, 5), (5, 3, 2))
    assert reference.combination_count == 28
    assert reference.link_counts == ((14, 13, 13),) * 3


def test_reference_backend_also_preserves_no_fee_parity():
    vectors = [
        ((10, 10), (8, 2, 3, 7), 3, ((2, 2, 2, 2), (2, 2, 2, 2))),
        ((10, 10), (8, 2, 2, 8), 5, ((3, 3, 3, 3), (3, 3, 3, 3))),
        ((10, 10), (5, 5, 5, 5), 7, ((4, 4, 4, 4), (4, 4, 4, 4))),
        ((5, 5), (5, 5), 3, ((2, 2), (2, 2))),
        ((5, 5, 5), (5, 5, 5), 16, ((8, 8, 8),) * 3),
        (
            (10, 10, 2),
            (8, 2, 2, 8, 2),
            28,
            ((16, 16, 13, 13, 13), (16, 16, 13, 13, 13), (7, 7, 14, 14, 14)),
        ),
        ((5, 5, 10), (5, 5, 10), 9, ((8, 4, 4), (4, 5, 5), (4, 5, 5))),
    ]
    for inputs, outputs, count, matrix in vectors:
        result = boltzmann_reference_analysis(inputs, outputs)
        assert (result.combination_count, result.link_counts) == (count, matrix)


def test_merge_fees_reproduces_the_official_synthetic_output_semantics():
    result = boltzmann_reference_analysis((5, 5, 5), (5, 3, 2), merge_fees=True)
    assert result.observed_fee == 5
    assert result.outputs == (5, 5, 3, 2)
    assert result.fee_output_index == 1
    assert result.combination_count == 16
    assert result.link_counts == ((8, 8, 8, 8),) * 3


def test_merge_fees_can_make_every_link_deterministic_like_the_reference():
    result = boltzmann_reference_analysis((10, 7), (8, 6), merge_fees=True)
    assert result.outputs == (8, 6, 3)
    assert result.fee_output_index == 2
    assert result.combination_count == 1
    assert result.link_counts == ((1, 1, 1), (1, 1, 1))


def test_linked_inputs_reproduce_official_pack_and_expansion():
    result = boltzmann_reference_with_linked_inputs(
        (5, 5, 5), (5, 5, 5), [{0, 1}]
    )
    assert result.combination_count == 4
    assert result.inputs == (5, 5, 5)
    assert result.link_counts == ((3, 3, 3), (3, 3, 3), (2, 2, 2))
    assert result.linked_input_groups == ((0, 1),)


def test_linked_inputs_preserve_reference_unpack_order_for_asymmetric_values():
    result = boltzmann_reference_with_linked_inputs(
        (8, 5, 3), (7, 5, 3), [{0, 2}]
    )
    assert result.combination_count == 2
    assert result.inputs == (8, 3, 5)
    assert result.link_counts == ((2, 1, 2), (2, 1, 2), (1, 2, 1))


def test_overlapping_owner_groups_are_transitively_merged():
    result = boltzmann_reference_with_linked_inputs(
        (4, 4, 4), (6, 5), [{0, 1}, {1, 2}]
    )
    assert result.linked_input_groups == ((0, 1, 2),)
    assert result.combination_count == 1
    assert result.link_counts == ((1, 1),) * 3


def test_precheck_exposes_deterministic_links_without_changing_linkability():
    ordinary = boltzmann_reference_analysis((1, 2), (1, 2))
    checked = boltzmann_reference_analysis((1, 2), (1, 2), precheck=True)

    assert checked.combination_count == ordinary.combination_count == 2
    assert checked.link_counts == ordinary.link_counts == ((2, 1), (1, 2))
    assert checked.precheck_deterministic_links == ((0, 0), (1, 1))


def test_precheck_links_expand_across_packed_inputs():
    result = boltzmann_reference_with_linked_inputs(
        (1, 1, 1), (1, 2), [{0, 1}], precheck=True
    )

    assert result.inputs == (1, 1, 1)
    assert result.precheck_deterministic_links == ((0, 0), (1, 0), (2, 1))


def test_joinmarket_intrafees_widen_the_reference_matching_interval():
    ordinary = boltzmann_reference_analysis((10, 10), (8, 2, 3, 7))
    bounded = boltzmann_reference_analysis(
        (10, 10), (8, 2, 3, 7), intrafees=(1, 2), precheck=True
    )

    assert ordinary.combination_count == 3
    assert bounded.combination_count == 5
    assert bounded.link_counts == ((3, 3, 3, 3),) * 2
    assert bounded.precheck_deterministic_links == ()
    assert bounded.intrafees == (1.0, 2.0)


@pytest.mark.parametrize("intrafees", [(-1, 0), (0, float("inf")), (True, 0), (1,)])
def test_intrafees_reject_invalid_bounds(intrafees):
    with pytest.raises(ValueError, match="intrafee"):
        boltzmann_reference_analysis((2, 1), (2, 1), intrafees=intrafees)
