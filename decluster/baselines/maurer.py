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


def exact_subtransaction_mappings(inputs, outputs, *, max_coins=12):
    """Enumerate all exact, non-empty input/output block mappings.

    Each input and output occurs in exactly one block and each block independently
    conserves value.  The all-coins/single-owner interpretation is included.  The
    bound is explicit because exhaustive set-partition enumeration is exponential.
    """
    inputs, outputs = tuple(inputs), tuple(outputs)
    if not inputs or not outputs:
        return ()
    if any(value < 0 for value in inputs + outputs):
        raise ValueError("coin values must be non-negative")
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
