import random

import pytest

from decluster.declustering import decluster
from decluster.partition import Partition


def table_weight(pairs, default=0.0):
    """A weight function reading a dict keyed by unordered pairs."""
    lookup = {frozenset(pair): value for pair, value in pairs.items()}
    return lambda a, b: lookup.get(frozenset((a, b)), default)


def test_a_positive_threshold_is_refused():
    with pytest.raises(ValueError):
        decluster(Partition([[1, 2]]), lambda a, b: 0.0, cut_below=0.5)


def test_evidence_for_a_pairing_never_cuts_it():
    inherited = Partition([[1, 2, 3], [4, 5]])
    result = decluster(inherited, lambda a, b: 4.0, cut_below=-1.0)
    assert result.partition == inherited
    assert result.cut == ()


def test_two_groups_with_evidence_against_each_other_are_separated():
    weight = table_weight(
        {(1, 2): 5.0, (3, 4): 5.0} | {pair: -4.0 for pair in ((1, 3), (1, 4), (2, 3), (2, 4))}
    )
    result = decluster(Partition([[1, 2, 3, 4]]), weight, cut_below=-1.0)
    assert result.partition == Partition([[1, 2], [3, 4]])
    outcome, = result.cut
    assert (outcome.interior_weight, outcome.severed_weight) == (10.0, -16.0)


def test_one_negative_pair_does_not_carry_a_cut_the_block_argues_against():
    # Admissibility is between groups: 1 owes -3 to 2 but +5 to 3, so no split clears the bar.
    weight = table_weight({(1, 2): -3.0, (1, 3): 5.0, (2, 3): 5.0})
    result = decluster(Partition([[1, 2, 3]]), weight, cut_below=-1.0)
    assert result.partition == Partition([[1, 2, 3]])


def test_evidence_against_every_pairing_shatters_the_block():
    result = decluster(Partition([[1, 2, 3]]), lambda a, b: -5.0, cut_below=-1.0)
    assert result.partition == Partition.discrete([1, 2, 3])


def test_two_equally_supported_cuts_leave_the_block_whole():
    # 1|23 and 2|13 both sever -2 and keep 8; naming either would place a boundary evidence does not.
    weight = table_weight({(1, 2): -10.0, (1, 3): 8.0, (2, 3): 8.0})
    result = decluster(Partition([[1, 2, 3]]), weight, cut_below=-1.0)
    assert result.partition == Partition([[1, 2, 3]])
    assert result.cut == ()


def test_a_block_too_large_to_search_is_left_whole_and_counted():
    block = list(range(6))
    result = decluster(Partition([block]), lambda a, b: -5.0, cut_below=-1.0, max_block=5)
    assert result.partition == Partition([block])
    assert result.unsearched == (frozenset(block),)
    assert result.summary()["unsearched"] == 1


def test_singletons_are_neither_cut_nor_counted_as_searched():
    result = decluster(Partition.discrete([1, 2, 3]), lambda a, b: -5.0, cut_below=-1.0)
    assert result.partition == Partition.discrete([1, 2, 3])
    assert result.outcomes == () and result.unsearched == ()


def test_a_stricter_threshold_never_cuts_more():
    weight = table_weight({(1, 2): -2.0, (1, 3): -6.0, (2, 3): -6.0})
    lenient = decluster(Partition([[1, 2, 3]]), weight, cut_below=-1.0).partition
    strict = decluster(Partition([[1, 2, 3]]), weight, cut_below=-5.0).partition
    assert lenient < strict


def test_the_result_only_ever_refines_the_partition_it_was_given():
    rng = random.Random(17)
    for _ in range(40):
        labels = {element: rng.randrange(1, 4) for element in range(8)}
        inherited = Partition.from_lookup(labels)
        pairs = {
            (a, b): rng.uniform(-6.0, 6.0) for a in range(8) for b in range(a + 1, 8)
        }
        result = decluster(inherited, table_weight(pairs), cut_below=-1.0)
        assert result.partition.refines(inherited)


def test_the_threshold_travels_with_the_result():
    result = decluster(Partition([[1, 2]]), lambda a, b: -9.0, cut_below=-2.5)
    assert result.cut_below == -2.5 and result.summary()["cut_below"] == -2.5
