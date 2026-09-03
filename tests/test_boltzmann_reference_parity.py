"""Parity probes transcribed from Samourai-Wallet/boltzmann's official tests.

Expected values were recomputed with commit ed0b649c6ca4abf0cecb69467de6c4e97e847904 and
``options=[LINKABILITY]``. The reference matrix is transposed here to local input-by-output order.
"""

from decluster.baselines.boltzmann import fee_tolerant_link_analysis


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


def test_fee_vector_records_the_remaining_boltzmann_multiplicity_gap():
    # Official TEST P3 with fees reports 28 combinations and each input linked
    # 14/13/13 times to outputs 5/3/2. The local unique-mapping family has 19;
    # Boltzmann's traversal assigns multiplicity to fee-compatible readings.
    count, matrix = _local_counts((5, 5, 5), (5, 3, 2))
    assert (count, matrix) == (19, ((10, 9, 9), (10, 9, 9), (10, 9, 9)))
    assert count != 28
    assert matrix != ((14, 13, 13),) * 3
