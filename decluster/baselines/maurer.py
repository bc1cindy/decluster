"""Exact balanced sub-transaction mappings.

This is the deliberately narrow reference baseline: every participant block must
balance exactly.  Fees, amount tolerances, roundness, and contextual priors are
outside this module.
"""

from dataclasses import dataclass
from itertools import permutations


@dataclass(frozen=True)
class ExactMapping:
    """One mapping, represented as canonical input/output index blocks."""

    blocks: tuple[tuple[tuple[int, ...], tuple[int, ...]], ...]


def _partitions(items):
    """Yield every set partition once, with canonical block ordering."""
    if not items:
        yield ()
        return
    first, *rest = items
    for partition in _partitions(rest):
        yield ((first,),) + partition
        for index in range(len(partition)):
            blocks = list(partition)
            blocks[index] = tuple(sorted((first,) + blocks[index]))
            yield tuple(sorted(blocks, key=lambda block: block[0]))


def _canonical(blocks):
    return ExactMapping(tuple(sorted(blocks, key=lambda pair: (pair[0], pair[1]))))


def mapping_refines(finer, coarser):
    """Return whether ``finer`` can produce ``coarser`` by merging blocks.

    Maurer et al. call the coarser mapping *derived*.  Containment must hold on
    both the input and output side of the same paired block; comparing only the
    number of blocks is insufficient because refinement-maximal mappings need
    not all have the globally largest block count.
    """

    return all(
        any(
            set(input_block) <= set(other_inputs)
            and set(output_block) <= set(other_outputs)
            for other_inputs, other_outputs in coarser.blocks
        )
        for input_block, output_block in finer.blocks
    )


def non_derived_mappings(mappings):
    """Keep mappings that no distinct valid mapping strictly refines.

    This is the family used for the linkability evaluation in Maurer et al.;
    the paper excludes derived mappings because merging participant blocks adds
    no new information.  ``exact_subtransaction_mappings`` intentionally keeps
    returning the full family so existing callers do not change semantics.
    """

    mappings = tuple(mappings)
    return tuple(
        mapping
        for mapping in mappings
        if not any(
            other.blocks != mapping.blocks and mapping_refines(other, mapping)
            for other in mappings
        )
    )


def exact_non_derived_mappings(inputs, outputs, *, max_coins=12):
    """Enumerate Maurer et al.'s exact non-derived mapping family."""

    return non_derived_mappings(
        exact_subtransaction_mappings(inputs, outputs, max_coins=max_coins)
    )


def exact_subtransaction_mappings(inputs, outputs, *, max_coins=12):
    """Enumerate all exact, non-empty input/output block mappings.

    Each input and output occurs in exactly one block and each block independently
    conserves value.  The all-coins/single-owner interpretation is included.  The
    bound is explicit because exhaustive set-partition enumeration is exponential.

    Values must be integers: the paper's coin domain is satoshis, and binary
    floating point silently breaks exact conservation.  ``0.1 + 0.2 + 0.4`` is
    not ``0.7``, so a float-valued transaction loses mappings without error.
    """
    inputs, outputs = tuple(inputs), tuple(outputs)
    if not inputs or not outputs:
        return ()
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
           for value in inputs + outputs):
        raise ValueError("coin values must be non-negative integers")
    if len(inputs) + len(outputs) > max_coins:
        raise ValueError("exact baseline exceeds max_coins")
    if sum(inputs) != sum(outputs):
        return ()

    input_partitions = tuple(_partitions(list(range(len(inputs)))))
    output_partitions = tuple(_partitions(list(range(len(outputs)))))
    mappings = set()
    for in_blocks in input_partitions:
        for out_blocks in output_partitions:
            if len(in_blocks) != len(out_blocks):
                continue
            in_sums = [sum(inputs[i] for i in block) for block in in_blocks]
            for permuted_outputs in permutations(out_blocks):
                if all(in_sums[k] == sum(outputs[j] for j in out_block)
                       for k, out_block in enumerate(permuted_outputs)):
                    mappings.add(_canonical(tuple(zip(in_blocks, permuted_outputs))))
    return tuple(sorted(mappings, key=lambda mapping: mapping.blocks))
