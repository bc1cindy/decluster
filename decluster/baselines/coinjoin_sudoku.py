"""Independent reconstruction of the amount grouping described by CoinJoin Sudoku.

The historical analyzer was not published in the cited repository. This module
therefore implements only the mechanism stated in the advisory: partition both
transaction sides into non-empty groups and retain equal-sum pairings. Selection,
weighting and the fee model are separate, explicitly local adaptations. This module
does not reproduce the digit-skipping optimization or historical SharedCoin result.

Source: `sudoku` in `catalog/ctp-sources.json`. The original analyzer was never published,
so this reconstructs the grouping it describes rather than porting it.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations


@dataclass(frozen=True)
class SudokuMapping:
    """One canonical pairing of input and output index groups."""

    blocks: tuple[tuple[tuple[int, ...], tuple[int, ...]], ...]


def _partitions(items):
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


def _fee_outputs(inputs, outputs, fee_unit, max_outputs):
    fee = sum(inputs) - sum(outputs)
    if fee < 0:
        return None
    if fee == 0:
        return outputs
    if fee_unit is None or fee_unit <= 0 or fee % fee_unit:
        return None
    fee_count = fee // fee_unit
    if fee_count > max_outputs - len(outputs):
        raise ValueError("nominal Sudoku reconstruction exceeds max_coins")
    return outputs + (fee_unit,) * fee_count


def equal_sum_groupings(inputs, outputs, *, fee_unit=None, max_coins=12):
    """Enumerate every indexed equal-sum grouping described by the advisory.

    ``fee_unit`` is a LOCAL fee model, not a published rule. The advisory states only that the
    fee is a multiple of a constant (currently 0.0001 BTC) and shows it as a single amount beside
    the outputs; splitting it into that many equal pseudo-outputs so groups can balance is this
    module's choice, and it decides the result — the same transaction read with one pseudo-output
    of the whole fee admits only the trivial grouping. The unavailable analyzer leaves its grouping
    deduplication semantics unspecified, so equal-valued coins and fee units remain distinct by
    index here.
    """
    inputs, outputs = tuple(inputs), tuple(outputs)
    if not inputs or not outputs:
        return ()
    if not isinstance(max_coins, int) or isinstance(max_coins, bool) or max_coins < 2:
        raise ValueError("max_coins must be an integer of at least two")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value <= 0
        for value in inputs + outputs
    ):
        raise ValueError("coin values must be positive integers")
    if len(inputs) + len(outputs) > max_coins:
        raise ValueError("nominal Sudoku reconstruction exceeds max_coins")
    balanced_outputs = _fee_outputs(
        inputs, outputs, fee_unit, max_coins - len(inputs)
    )
    if balanced_outputs is None:
        return ()
    mappings = set()
    input_partitions = tuple(_partitions(tuple(range(len(inputs)))))
    output_partitions = tuple(_partitions(tuple(range(len(balanced_outputs)))))
    for input_blocks in input_partitions:
        for output_blocks in output_partitions:
            if len(input_blocks) != len(output_blocks):
                continue
            input_sums = tuple(
                sum(inputs[index] for index in block) for block in input_blocks
            )
            for candidate in permutations(output_blocks):
                if not all(
                    input_sums[position]
                    == sum(balanced_outputs[index] for index in output_block)
                    for position, output_block in enumerate(candidate)
                ):
                    continue
                mapping = SudokuMapping(tuple(sorted(zip(input_blocks, candidate))))
                mappings.add(mapping)
    return tuple(sorted(mappings, key=lambda mapping: mapping.blocks))


def maximally_separated_groupings(inputs, outputs, *, fee_unit=None, max_coins=12):
    """Local adaptation retaining groupings with the largest participant count."""
    mappings = equal_sum_groupings(
        inputs, outputs, fee_unit=fee_unit, max_coins=max_coins
    )
    if not mappings:
        return ()
    largest = max(len(mapping.blocks) for mapping in mappings)
    return tuple(mapping for mapping in mappings if len(mapping.blocks) == largest)


def uniform_link_probabilities(inputs, outputs, *, fee_unit=None, max_coins=12):
    """Local uniform marginals over maximally separated indexed groupings."""
    mappings = maximally_separated_groupings(
        inputs, outputs, fee_unit=fee_unit, max_coins=max_coins
    )
    if not mappings:
        return ()
    denominator = len(mappings)
    return tuple(
        tuple(
            sum(
                any(
                    input_index in input_block and output_index in output_block
                    for input_block, output_block in mapping.blocks
                )
                for mapping in mappings
            )
            / denominator
            for output_index in range(len(outputs))
        )
        for input_index in range(len(inputs))
    )


def collapse_fee_permutations(mappings, real_output_count):
    """Collapse mappings differing only in indexed pseudo-output identities."""
    return {
        tuple(
            sorted(
                (
                    input_block,
                    tuple(index for index in output_block if index < real_output_count),
                    sum(index >= real_output_count for index in output_block),
                )
                for input_block, output_block in mapping.blocks
            )
        )
        for mapping in mappings
    }
