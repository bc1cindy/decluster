"""The descending pass: cut a partition this module did not build.

A clusterer owns every merge it made, so refusing a merge before making it is enough to keep two
owners apart. An inherited partition offers no such control — the merges are already there, made
by a criterion that cannot be inspected — so keeping owners apart requires cutting instead.

Cutting is held to a stricter standard than merging, and deliberately so. Refusing a merge decides
on evidence the analyst gathered; cutting an inherited block contradicts a claim whose basis is
unavailable, and a cut made on absent evidence invents privacy rather than measuring it. So
`cut_below` has no default: the caller states how much aggregate evidence against a pairing is
enough to overturn someone else's claim, and the number travels in the result.

Blocks larger than `max_block` are left whole and counted, because a block that could not be
searched is not a block that was found homogeneous.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from .partition import Partition

# Bell(9) = 21147 candidates over at most 36 pairs. Past this the exact search stops paying for
# itself and a sampler is the better instrument.
MAX_BLOCK = 9


@dataclass(frozen=True)
class BlockOutcome:
    """What the pass did with one block, and the evidence it acted on."""

    members: frozenset
    groups: tuple[frozenset, ...]
    interior_weight: float
    severed_weight: float

    @property
    def was_cut(self):
        return len(self.groups) > 1


@dataclass(frozen=True)
class DeclusterResult:
    partition: Partition
    outcomes: tuple[BlockOutcome, ...]
    unsearched: tuple[frozenset, ...]
    cut_below: float

    @property
    def cut(self):
        return tuple(outcome for outcome in self.outcomes if outcome.was_cut)

    def summary(self):
        return {
            "blocks": len(self.outcomes) + len(self.unsearched),
            "cut": len(self.cut),
            "left_whole": len(self.outcomes) - len(self.cut),
            "unsearched": len(self.unsearched),
            "severed_weight": sum(outcome.severed_weight for outcome in self.cut),
            "cut_below": self.cut_below,
        }


def _set_partitions(items):
    """Every partition of `items` as a tuple of tuples, in a deterministic order."""
    if not items:
        yield ()
        return
    first, *rest = items
    for partition in _set_partitions(rest):
        yield ((first,), *partition)
        for index in range(len(partition)):
            blocks = list(partition)
            blocks[index] = (first, *blocks[index])
            yield tuple(blocks)


def _pairwise(members, weight):
    """The weight of every pair in the block, evaluated once."""
    return {
        frozenset(pair): weight(*pair) for pair in combinations(sorted(members, key=repr), 2)
    }


def _across(left, right, table):
    return sum(table[frozenset((a, b))] for a in left for b in right)


def _split(candidate, table, cut_below):
    """Interior and severed weight of a candidate, or None when it cuts on too little evidence.

    Admissibility is checked between whole groups rather than between single pairs: that is what
    stops one strongly negative pair from carrying a cut the rest of the block argues against.
    """
    severed = 0.0
    for left, right in combinations(candidate, 2):
        between = _across(left, right, table)
        if between > cut_below:
            return None
        severed += between
    interior = sum(total for total in table.values()) - severed
    return interior, severed


def _best_cut(members, weight, cut_below):
    """The admissible partition of `members` holding the most evidence inside its groups.

    A tie between two admissible cuts is resolved by not cutting. Picking either one would name a
    boundary the evidence does not place, and an arbitrary boundary reads downstream exactly like a
    measured one.
    """
    table = _pairwise(members, weight)
    whole = (tuple(sorted(members, key=repr)),)
    best, best_interior, best_severed, ties = whole, sum(table.values()), 0.0, 1
    for candidate in _set_partitions(list(whole[0])):
        if len(candidate) == 1:
            continue
        scored = _split(candidate, table, cut_below)
        if scored is None:
            continue
        interior, severed = scored
        if interior > best_interior:
            best, best_interior, best_severed, ties = candidate, interior, severed, 1
        elif interior == best_interior:
            ties += 1
    if ties > 1:
        return (frozenset(members),), sum(table.values()), 0.0
    return tuple(frozenset(group) for group in best), best_interior, best_severed


def decluster(partition, weight, *, cut_below, max_block=MAX_BLOCK):
    """Refine `partition` where the evidence overturns the merges it inherited.

    `weight(a, b)` returns signed bits for a pair and must **not** include a co-spend prior: the
    co-spend is the inherited claim under test, not evidence for it. The result is a meet with
    `partition`, so it can only be finer.
    """
    if cut_below > 0:
        raise ValueError("cut_below must be at most zero; a cut needs evidence against a pairing")

    outcomes, unsearched, blocks = [], [], []
    for block in partition.blocks():
        if len(block) < 2 or len(block) > max_block:
            if len(block) > max_block:
                unsearched.append(block)
            blocks.append(block)
            continue
        groups, interior, severed = _best_cut(block, weight, cut_below)
        outcomes.append(BlockOutcome(block, groups, interior, severed))
        blocks.extend(groups)

    return DeclusterResult(
        partition.meet(Partition(blocks)), tuple(outcomes), tuple(unsearched), cut_below
    )
