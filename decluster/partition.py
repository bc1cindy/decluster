"""The partition refinement lattice as a first-class object.

Clustering moves up this lattice: union-find fuses blocks and can never split one, so a clusterer
built that way owns every merge it made. Declustering moves down: it takes a partition it did not
build and cuts blocks that the evidence says hold more than one owner. The two directions need the
same object, so it lives here rather than inside either.

`join` divides only where both sides divide, so it is the coarser of the two — the direction a
merge pass travels. `meet` divides wherever either side divides, so it is the finer — the direction
a refinement pass travels. Ordering is by refinement: `a <= b` when every block of `a` sits inside
a block of `b`.

Both operations are defined over one ground set. Combining partitions of different sets is refused
rather than resolved, because every silent resolution of that mismatch invents an answer.
"""

from __future__ import annotations

from .unionfind import UF


class GroundSetMismatch(ValueError):
    """Two partitions cover different elements, so no lattice operation between them is defined."""


class Partition:
    """An immutable partition of a finite set, comparable and hashable."""

    __slots__ = ("_blocks", "_index")

    def __init__(self, blocks):
        collected, index = [], {}
        for block in blocks:
            members = frozenset(block)
            if not members:
                continue
            for element in members:
                if element in index:
                    raise ValueError(f"element in more than one block: {element!r}")
                index[element] = members
            collected.append(members)
        self._blocks = frozenset(collected)
        self._index = index

    # --- construction ---------------------------------------------------------------------

    @classmethod
    def from_lookup(cls, mapping):
        """From `element -> label`, the shape `views.cluster_addresses` returns."""
        blocks = {}
        for element, label in mapping.items():
            blocks.setdefault(label, []).append(element)
        return cls(blocks.values())

    @classmethod
    def from_union_find(cls, uf: UF):
        return cls(uf.groups())

    @classmethod
    def discrete(cls, elements):
        """Every element alone: the finest partition, the bottom of the lattice."""
        return cls([element] for element in elements)

    @classmethod
    def trivial(cls, elements):
        """One block: the coarsest partition, the top of the lattice."""
        elements = frozenset(elements)
        return cls([elements] if elements else [])

    # --- reading --------------------------------------------------------------------------

    def blocks(self):
        return self._blocks

    def elements(self):
        return frozenset(self._index)

    def block(self, element):
        """The block holding `element`, or None when the partition does not cover it."""
        return self._index.get(element)

    def same_block(self, a, b):
        block = self._index.get(a)
        return block is not None and b in block

    # --- lattice --------------------------------------------------------------------------

    def _require_same_ground(self, other):
        if self.elements() != other.elements():
            raise GroundSetMismatch(
                f"{len(self.elements())} elements against {len(other.elements())}"
            )

    def meet(self, other):
        """Divide wherever either side divides: blocks are the non-empty intersections."""
        self._require_same_ground(other)
        parts = {}
        for element, block in self._index.items():
            parts.setdefault((block, other._index[element]), []).append(element)
        return Partition(parts.values())

    def join(self, other):
        """Divide only where both sides divide: the transitive closure of the two relations."""
        self._require_same_ground(other)
        uf = UF(self._index)
        for source in (self, other):
            for block in source._blocks:
                members = iter(block)
                first = next(members)
                for element in members:
                    uf.union(first, element)
        return Partition.from_union_find(uf)

    def refines(self, other):
        """Whether every block here sits inside a block of `other` — this partition is finer."""
        self._require_same_ground(other)
        return all(block <= other._index[next(iter(block))] for block in self._blocks)

    # --- protocol -------------------------------------------------------------------------

    __and__ = meet
    __or__ = join
    __le__ = refines

    def __lt__(self, other):
        return self != other and self.refines(other)

    def __eq__(self, other):
        return isinstance(other, Partition) and self._blocks == other._blocks

    def __hash__(self):
        return hash(self._blocks)

    def __len__(self):
        return len(self._blocks)

    def __iter__(self):
        return iter(self._blocks)

    def __repr__(self):
        return f"Partition({len(self._blocks)} blocks over {len(self._index)} elements)"
