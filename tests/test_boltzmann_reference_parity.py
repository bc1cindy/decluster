"""Parity probes transcribed from Samourai-Wallet/boltzmann's official tests.

Expected values were recomputed with commit ed0b649c6ca4abf0cecb69467de6c4e97e847904 and
``options=[LINKABILITY]``. The reference matrix is transposed here to local input-by-output order.
"""

from decluster.baselines.boltzmann import fee_tolerant_link_analysis
from decluster.baselines.boltzmann_reference import boltzmann_reference_analysis


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
