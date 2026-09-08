"""Small, dependency-free port of Boltzmann's aggregate traversal.

The public result deliberately exposes integer multiplicities.  They are not
the same object as Maurer's set of canonical sub-transaction mappings: when a
transaction pays a fee, Boltzmann's decomposition tree can assign more than one
occurrence to the same terminal partition.

This implements default ``LINKABILITY`` plus explicit ``MERGE_FEES``,
``PRECHECK``, known-owner input packing and JoinMarket intrafee bounds.  The
upstream ``MERGE_OUTPUTS`` option is not ported: in the pinned reference
revision it is documented as unreliable and its packer only examines inputs.

Two upstream layers above the traversal are also absent.  Intrafee bounds must
be supplied by the caller: the reference derives them from a maximum intrafee
ratio by first testing the transaction for a CoinJoin output pattern and
estimating the participant count, and neither the test nor the derivation is
ported, so nothing here decides *whether* a transaction is a CoinJoin or what
its intrafees would be.  Known-owner input groups are likewise given, not
recovered from shared addresses.

Source: `boltzmann` in `catalog/ctp-sources.json` — LaurentMT, *Boltzmann* (2015).
This is the port; `baselines.boltzmann` is the analysis built on top of it.
"""

from collections import defaultdict, deque
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class BoltzmannReferenceAnalysis:
    """Counts plus the optional diagnostic state of the pinned reference modes.

    ``precheck_deterministic_links`` uses this module's input-by-output matrix
    order. Intrafees are the maximum maker receipt and taker payment accepted
    by the reference matching predicate; they are bounds, not observed fees.
    """

    combination_count: int
    link_counts: tuple[tuple[int, ...], ...]
    probabilities: tuple[tuple[float, ...], ...]
    observed_fee: int
    inputs: tuple[int, ...]
    outputs: tuple[int, ...]
    merge_fees: bool = False
    fee_output_index: int | None = None
    linked_input_groups: tuple[tuple[int, ...], ...] = ()
    precheck_deterministic_links: tuple[tuple[int, int], ...] = ()
    intrafees: tuple[float, float] = (0.0, 0.0)


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


def _validated_intrafees(intrafees):
    try:
        maker, taker = intrafees
    except (TypeError, ValueError) as exc:
        raise ValueError("intrafees must contain maker and taker bounds") from exc
    if any(isinstance(value, bool) or not isinstance(value, (int, float))
           or not isfinite(value) or value < 0 for value in (maker, taker)):
        raise ValueError("intrafee bounds must be finite non-negative numbers")
    return float(maker), float(taker)


def boltzmann_reference_analysis(
    inputs, outputs, *, max_coins=12, merge_fees=False, precheck=False,
    intrafees=(0, 0),
):
    """Reproduce Boltzmann's default aggregate traversal and link matrix.

    Values must be non-negative integers and the observed transaction fee must
    be non-negative. The bound applies to each side, matching the reference
    tool's ``max_txos`` guard rather than Maurer's combined-coin bound.
    ``precheck`` exposes the reference aggregate test. The reference then repacks
    the deterministic links it finds before running the exhaustive traversal, and
    this port does not. Across every zero- and positive-fee transaction of up to
    four coins a side, that repacking changed neither the combination count nor
    any link count; what it does change is the order of the returned coins, since
    a pack is reinserted where it sat rather than at its descending-value
    position. So callers must not read ``inputs`` positionally as reference order
    under ``precheck``. The two intrafee bounds are accepted only as an explicit
    hypothesis and disable precheck, as in the pinned implementation.
    """

    inputs, outputs = tuple(inputs), tuple(outputs)
    intrafees = _validated_intrafees(intrafees)
    values = inputs + outputs
    if not inputs or not outputs:
        return BoltzmannReferenceAnalysis(
            0, (), (), 0, inputs, outputs, merge_fees, None,
            intrafees=intrafees,
        )
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
           for value in values):
        raise ValueError("coin values must be non-negative integers")
    fee = sum(inputs) - sum(outputs)
    if fee < 0:
        return BoltzmannReferenceAnalysis(
            0, (), (), fee, inputs, outputs, merge_fees, None,
            intrafees=intrafees,
        )
    # The reference tool discards null-value txos (OP_RETURN and the like) before
    # any aggregate is formed, at both of its filter points.  Keeping them would
    # match every aggregate value and inflate the combination count.
    inputs = tuple(value for value in inputs if value > 0)
    outputs = tuple(value for value in outputs if value > 0)
    if not inputs or not outputs:
        return BoltzmannReferenceAnalysis(
            0, (), (), fee, inputs, outputs, merge_fees, None,
            intrafees=intrafees,
        )

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
            if intrafees == (0.0, 0.0) and difference < 0:
                break
            maker_fee, taker_fee = intrafees
            matches = (
                -maker_fee <= difference <= traversal_fee + taker_fee
                if intrafees != (0.0, 0.0)
                else difference <= traversal_fee
            )
            if matches:
                for mask, value in enumerate(in_values):
                    if value == left and mask not in input_value:
                        matching_inputs.append(mask)
                        input_value[mask] = left
                outputs_by_input_value[left].update(
                    mask for mask, value in enumerate(out_values) if value == right
                )
    matching_inputs.sort()
    deterministic_links = ()
    if precheck and intrafees == (0.0, 0.0) and matching_inputs:
        raw_counts = [[0] * len(outputs) for _ in inputs]
        input_occurrences = [0] * len(inputs)
        for input_mask in matching_inputs:
            value = input_value[input_mask]
            for output_mask in outputs_by_input_value[value]:
                _add_counts(
                    raw_counts,
                    _link_counts(input_mask, output_mask, len(inputs), len(outputs)),
                )
                for index in range(len(inputs)):
                    input_occurrences[index] += int(bool(input_mask & (1 << index)))
        reference_count = input_occurrences[0]
        deterministic_links = tuple(
            (input_index, output_index)
            for input_index, row in enumerate(raw_counts)
            for output_index, count in enumerate(row)
            if count == reference_count
        )
    if len(matching_inputs) < 2:
        return BoltzmannReferenceAnalysis(
            0, (), (), fee, inputs, outputs, merge_fees, fee_output_index,
            precheck_deterministic_links=deterministic_links,
            intrafees=intrafees,
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
        merge_fees, fee_output_index, (), deterministic_links, intrafees,
    )


def _merged_index_groups(groups, size):
    components = []
    for raw_group in groups:
        group = set(raw_group)
        if not group:
            continue
        if any(isinstance(index, bool) or not isinstance(index, int)
               or not 0 <= index < size for index in group):
            raise ValueError("linked input index out of range")
        touching = [component for component in components if component & group]
        for component in touching:
            group.update(component)
            components.remove(component)
        components.append(group)
    return tuple(tuple(sorted(group)) for group in sorted(components, key=lambda group: min(group)))


def boltzmann_reference_with_linked_inputs(
    inputs, outputs, linked_inputs, *, max_coins=12, merge_fees=False,
    precheck=False, intrafees=(0, 0),
):
    """Reproduce TxosLinker's input packing and matrix expansion.

    ``linked_inputs`` contains sets of original input indices. Overlapping sets
    are transitively merged. The aggregate traversal sees one summed input per
    group; afterward its row is replicated for every original member, exactly
    as the reference tool unpacks a known-owner input pack.
    """

    inputs = tuple(inputs)
    groups = _merged_index_groups(linked_inputs, len(inputs))
    # Null-value inputs are filtered before the reference packs known owners, so
    # they join no pack and occupy no row.  Caller indices still name the groups.
    kept = {index for index, value in enumerate(inputs) if value > 0}
    groups = tuple(
        kept_group
        for kept_group in (tuple(i for i in group if i in kept) for group in groups)
        if kept_group
    )
    grouped = {index for group in groups for index in group}
    entries = [((index,), inputs[index]) for index in sorted(kept - grouped)]
    entries.extend((group, sum(inputs[index] for index in group)) for group in groups)
    sorted_entries = sorted(entries, key=lambda entry: entry[1], reverse=True)
    analysis = boltzmann_reference_analysis(
        tuple(value for _, value in entries), outputs,
        max_coins=max_coins, merge_fees=merge_fees, precheck=precheck,
        intrafees=intrafees,
    )
    # The core uses the same stable descending sort as ``sorted_entries``.
    expanded_rows = []
    expanded_inputs = []
    expanded_precheck = []
    for packed_index, ((members, _), row) in enumerate(
        zip(sorted_entries, analysis.link_counts)
    ):
        for index in members:
            expanded_inputs.append(inputs[index])
            expanded_rows.append(row)
            expanded_precheck.append(packed_index)
    counts = tuple(expanded_rows)
    probabilities = tuple(
        tuple(value / analysis.combination_count for value in row) for row in counts
    ) if analysis.combination_count else ()
    deterministic = tuple(
        (expanded_index, output_index)
        for expanded_index, packed_index in enumerate(expanded_precheck)
        for candidate, output_index in analysis.precheck_deterministic_links
        if candidate == packed_index
    )
    return BoltzmannReferenceAnalysis(
        analysis.combination_count, counts, probabilities, analysis.observed_fee,
        tuple(expanded_inputs), analysis.outputs, analysis.merge_fees,
        analysis.fee_output_index, groups, deterministic,
        analysis.intrafees,
    )
