import random

import pytest

from decluster.partition import GroundSetMismatch, Partition
from decluster.unionfind import UF


GROUND = tuple(range(6))


def random_partition(rng, elements=GROUND):
    labels = [rng.randrange(1, len(elements) + 1) for _ in elements]
    return Partition.from_lookup(dict(zip(elements, labels)))


def sample(seed, count=40):
    rng = random.Random(seed)
    return [random_partition(rng) for _ in range(count)]


def test_blocks_partition_the_ground_set():
    p = Partition([[1, 2], [3]])
    assert p.elements() == {1, 2, 3}
    assert p.block(1) == {1, 2}
    assert p.same_block(1, 2) and not p.same_block(1, 3)


def test_an_element_in_two_blocks_is_refused():
    with pytest.raises(ValueError):
        Partition([[1, 2], [2, 3]])


def test_empty_blocks_are_dropped_rather_than_kept():
    assert Partition([[1], [], [2]]) == Partition([[1], [2]])


def test_lookup_and_union_find_agree():
    uf = UF([1, 2, 3])
    uf.union(1, 2)
    assert Partition.from_union_find(uf) == Partition.from_lookup({1: "a", 2: "a", 3: "b"})


def test_discrete_is_the_bottom_and_trivial_the_top():
    bottom, top = Partition.discrete(GROUND), Partition.trivial(GROUND)
    for p in sample(0):
        assert bottom.refines(p) and p.refines(top)
    assert len(bottom) == len(GROUND) and len(top) == 1


def test_join_divides_only_where_both_divide():
    # Yuval's whiteboard case: A cuts 1|2|34, B cuts 12|34. Only the 2|3 cut is in both.
    a = Partition([[1], [2], [3, 4]])
    b = Partition([[1, 2], [3, 4]])
    assert a.join(b) == Partition([[1, 2], [3, 4]])
    assert a.meet(b) == Partition([[1], [2], [3, 4]])


def test_meet_is_finer_and_join_is_coarser():
    for p, q in zip(sample(1), sample(2)):
        assert (p & q).refines(p) and (p & q).refines(q)
        assert p.refines(p | q) and q.refines(p | q)


def test_meet_is_the_greatest_lower_bound():
    for p, q, r in zip(sample(3), sample(4), sample(5)):
        if r.refines(p) and r.refines(q):
            assert r.refines(p & q)


def test_join_is_the_least_upper_bound():
    for p, q, r in zip(sample(6), sample(7), sample(8)):
        if p.refines(r) and q.refines(r):
            assert (p | q).refines(r)


def test_the_operations_are_commutative_idempotent_and_absorbing():
    for p, q in zip(sample(9), sample(10)):
        assert p & q == q & p and p | q == q | p
        assert p & p == p and p | p == p
        assert p & (p | q) == p and p | (p & q) == p


def test_the_operations_are_associative():
    for p, q, r in zip(sample(11), sample(12), sample(13)):
        assert (p & q) & r == p & (q & r)
        assert (p | q) | r == p | (q | r)


def test_refinement_is_a_partial_order():
    partitions = sample(14)
    for p in partitions:
        assert p.refines(p) and not p < p
    for p, q in zip(partitions, sample(15)):
        if p.refines(q) and q.refines(p):
            assert p == q


def test_a_different_ground_set_is_refused_rather_than_resolved():
    p, q = Partition([[1, 2]]), Partition([[1, 2, 3]])
    for operation in (Partition.meet, Partition.join, Partition.refines):
        with pytest.raises(GroundSetMismatch):
            operation(p, q)


def test_clustering_only_ever_moves_up():
    # A merge pass can reach any coarsening of where it started and nothing below it.
    start = Partition([[1], [2], [3], [4]])
    uf = UF(start.elements())
    uf.union(1, 2)
    merged = Partition.from_union_find(uf)
    assert start < merged and not merged.refines(start)


def test_declustering_only_ever_moves_down():
    inherited = Partition([[1, 2, 3], [4]])
    cut = inherited & Partition([[1, 2], [3, 4]])
    assert cut < inherited
    assert cut == Partition([[1, 2], [3], [4]])
