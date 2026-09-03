"""Small, dependency-free port of Boltzmann's aggregate traversal.

The public result deliberately exposes integer multiplicities.  They are not
the same object as Maurer's set of canonical sub-transaction mappings: when a
transaction pays a fee, Boltzmann's decomposition tree can assign more than one
occurrence to the same terminal partition.

This implements the default ``LINKABILITY`` semantics only.  ``PRECHECK``,
known-owner merges, ``MERGE_FEES`` and JoinMarket intrafees remain separate
options and are not silently approximated here.
"""

from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class BoltzmannReferenceAnalysis:
    combination_count: int
    link_counts: tuple[tuple[int, ...], ...]
    probabilities: tuple[tuple[float, ...], ...]
    observed_fee: int
    inputs: tuple[int, ...]
    outputs: tuple[int, ...]
    merge_fees: bool = False
    fee_output_index: int | None = None


def _aggregate_values(values):
    return tuple(
        sum(value for index, value in enumerate(values) if mask & (1 << index))
        for mask in range(1 << len(values))
    )


def _link_counts(input_mask, output_mask, input_count, output_count):
    return tuple(
        tuple(int(bool(input_mask & (1 << i)) and bool(output_mask & (1 << o)))
              for o in range(output_count))
        for i in range(input_count)
    )


def _add_counts(target, source, multiplier=1):
    for i, row in enumerate(source):
        for o, value in enumerate(row):
            target[i][o] += value * multiplier


def boltzmann_reference_analysis(inputs, outputs, *, max_coins=12, merge_fees=False):
    """Reproduce Boltzmann's default aggregate traversal and link matrix.

    Values must be non-negative integers and the observed transaction fee must
    be non-negative.  The bound applies to each side, matching the reference
    tool's ``max_txos`` guard rather than Maurer's combined-coin bound.
    """

    inputs, outputs = tuple(inputs), tuple(outputs)
    values = inputs + outputs
    if not inputs or not outputs:
        return BoltzmannReferenceAnalysis(0, (), (), 0, inputs, outputs, merge_fees, None)
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
           for value in values):
        raise ValueError("coin values must be non-negative integers")
    fee = sum(inputs) - sum(outputs)
    if fee < 0:
        return BoltzmannReferenceAnalysis(0, (), (), fee, inputs, outputs, merge_fees, None)

    output_entries = [(value, False, index) for index, value in enumerate(outputs)]
    traversal_fee = fee
    if merge_fees and fee > 0:
        output_entries.append((fee, True, len(output_entries)))
        traversal_fee = 0
    if len(inputs) > max_coins or len(output_entries) > max_coins:
        raise ValueError("Boltzmann reference baseline exceeds max_coins")

    # TxosLinker sorts both sides by descending value before building its
    # matrix.  Expose that order in the result so asymmetric vectors can be
    # compared cell-for-cell without an implicit permutation.
    inputs = tuple(sorted(inputs, reverse=True))
    output_entries.sort(key=lambda entry: entry[0], reverse=True)
    outputs = tuple(entry[0] for entry in output_entries)
    fee_output_index = next(
        (index for index, entry in enumerate(output_entries) if entry[1]), None
    )

    in_values = _aggregate_values(inputs)
    out_values = _aggregate_values(outputs)
    unique_in_values = sorted(set(in_values))
    unique_out_values = sorted(set(out_values))

    matching_inputs = []
    input_value = {}
    outputs_by_input_value = defaultdict(set)
    for left in unique_in_values:
        for right in unique_out_values:
            difference = left - right
            if difference < 0:
                break
            if difference <= traversal_fee:
                for mask, value in enumerate(in_values):
                    if value == left and mask not in input_value:
                        matching_inputs.append(mask)
                        input_value[mask] = left
                outputs_by_input_value[left].update(
                    mask for mask, value in enumerate(out_values) if value == right
                )
    matching_inputs.sort()
    if len(matching_inputs) < 2:
        return BoltzmannReferenceAnalysis(
            0, (), (), fee, inputs, outputs, merge_fees, fee_output_index
        )

    target = matching_inputs[-1]
    interior = set(matching_inputs[1:-1])
    decompositions = defaultdict(list)
    for right in range(target + 1):
        if right not in interior:
            continue
        for left in range(min(right, target - right + 1)):
            if right & left == 0 and left in interior:
                decompositions[right + left].append((right, left))

    input_target = (1 << len(inputs)) - 1
    output_target = (1 << len(outputs)) - 1
    raw_links = defaultdict(int)
    initial_outputs = {output_target: {0: (1, 0)}}
    stack = deque([(0, 0, input_target, initial_outputs)])
    combination_count = 0

    while stack:
        index, previous_left, right_input, output_states = stack[-1]
        choices = decompositions[right_input]
        next_index = index
        descended = False
        for choice_index in range(index, len(choices)):
            next_index = choice_index
            left_input = choices[choice_index][1]
            if left_input > previous_left:
                next_right_input = choices[choice_index][0]
                next_states = defaultdict(dict)
                for right_output, left_outputs in output_states.items():
                    used_output = output_target - right_output
                    parent_count = sum(value[0] for value in left_outputs.values())
                    for left_output in outputs_by_input_value[input_value[left_input]]:
                        if used_output & left_output:
                            continue
                        next_used_output = used_output + left_output
                        next_right_output = output_target - next_used_output
                        if (next_used_output & next_right_output == 0
                                and next_right_output
                                in outputs_by_input_value[input_value[next_right_input]]):
                            next_states[next_right_output][left_output] = (parent_count, 0)
                stack[-1] = (choice_index + 1, previous_left, right_input, output_states)
                stack.append((0, left_input, next_right_input, next_states))
                descended = True
                break
            next_index = len(choices)
            break
        if descended:
            continue
        if next_index <= len(choices) - 1:
            continue

        _, left_input, right_input, output_states = stack.pop()
        if not stack:
            combination_count = output_states[output_target][0][1]
            continue
        parent_states = stack[-1][3]
        for right_output, left_outputs in output_states.items():
            for left_output, (parent_count, child_count) in left_outputs.items():
                occurrences = child_count + 1
                raw_links[(right_input, right_output)] += parent_count
                raw_links[(left_input, left_output)] += parent_count * occurrences
                parent_right_output = left_output + right_output
                for parent_left_output, (count, children) in list(
                        parent_states[parent_right_output].items()):
                    parent_states[parent_right_output][parent_left_output] = (
                        count, children + occurrences
                    )

    combination_count += 1
    counts = [[0] * len(outputs) for _ in inputs]
    _add_counts(
        counts,
        _link_counts(input_target, output_target, len(inputs), len(outputs)),
    )
    for (input_mask, output_mask), multiplicity in raw_links.items():
        _add_counts(
            counts,
            _link_counts(input_mask, output_mask, len(inputs), len(outputs)),
            multiplicity,
        )
    frozen_counts = tuple(tuple(row) for row in counts)
    probabilities = tuple(
        tuple(value / combination_count for value in row) for row in frozen_counts
    )
    return BoltzmannReferenceAnalysis(
        combination_count, frozen_counts, probabilities, fee, inputs, outputs,
        merge_fees, fee_output_index,
    )
