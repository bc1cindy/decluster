"""Uniform link-probability analysis over explicitly selected balance models.

This is not parity with the Boltzmann tool.  ``exact`` is the Maurer-style conservation oracle;
``fee_tolerant`` permits a non-negative fee allocation across participant blocks, bounded by a
caller-supplied total tolerance.  Roundness is deliberately not an admissibility rule or prior.

Because every block deficit here is non-negative, a block that receives more value than it
contributes is inexpressible, and that block is exactly the JoinMarket maker: the reference tool
admits it through a negative-difference bound (``diff >= -fees_maker``).  So the intrafee case
usually cited alongside this mechanism is outside this module, not merely untested.
``boltzmann_reference`` carries the reference intrafee interval; it is not modelled here.

Source: `boltzmann` in `catalog/ctp-sources.json` — LaurentMT, *Boltzmann* (2015),
the link-probability matrix this analysis is measured against rather than ported from.
"""

from dataclasses import dataclass
from itertools import permutations
from math import log2

from .maurer import _canonical, _partitions, exact_subtransaction_mappings


@dataclass(frozen=True)
class ExactLinkAnalysis:
    mappings: tuple
    matrix: tuple[tuple[float, ...], ...]
    entropy_bits: float
    deterministic_links: tuple[tuple[int, int], ...]
    balance_model: str = "exact"
    observed_fee: int = 0
    fee_tolerance: int = 0


@dataclass(frozen=True)
class SameBlockAnalysis:
    """Same-side link probabilities: Maurer's ``p_II`` and ``p_OO``."""

    mapping_count: int
    input_matrix: tuple[tuple[float, ...], ...]
    output_matrix: tuple[tuple[float, ...], ...]
    balance_model: str = "exact"
    observed_fee: int = 0
    fee_tolerance: int = 0


@dataclass(frozen=True)
class ExactLinkCandidate:
    """One marginal link, with its exact support before division."""

    counterpart_index: int
    mapping_count: int
    probability: float


@dataclass(frozen=True)
class ExactCoinLinkEvidence:
    """Raw per-coin evidence derived from exact mapping membership.

    ``candidate_count`` is the number of counterpart coins linked in at least
    one exact mapping.  ``max_link_probability`` is the largest marginal link
    probability, not a normalized privacy score.  The integer counts and the
    common ``mapping_count`` keep the calculation independently checkable.
    """

    role: str
    index: int
    value: int
    mapping_count: int
    candidates: tuple[ExactLinkCandidate, ...]
    candidate_count: int
    max_link_probability: float | None


@dataclass(frozen=True)
class ExactPerCoinLinkAnalysis:
    """Input- and output-side marginal evidence for one transaction."""

    mapping_count: int
    inputs: tuple[ExactCoinLinkEvidence, ...]
    outputs: tuple[ExactCoinLinkEvidence, ...]


def _link_counts(mappings, input_count, output_count):
    counts = [[0] * output_count for _ in range(input_count)]
    for mapping in mappings:
        for in_block, out_block in mapping.blocks:
            for input_index in in_block:
                for output_index in out_block:
                    counts[input_index][output_index] += 1
    return tuple(tuple(row) for row in counts)


def fee_tolerant_subtransaction_mappings(inputs, outputs, *, fee_tolerance, max_coins=12):
    """Enumerate mappings whose blocks conserve value after allocating the observed fee.

    For every block, input value must be at least output value; the block deficits necessarily sum
    to the transaction's observed fee. ``fee_tolerance`` caps that total and must be explicit.
    This models fee allocation, not amount rounding: no near-equality or roundness preference is
    introduced. The all-coins interpretation remains present when the transaction fee is allowed.
    """
    inputs, outputs = tuple(inputs), tuple(outputs)
    if not inputs or not outputs:
        return ()
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
           for value in inputs + outputs):
        raise ValueError("coin values must be non-negative integers")
    if isinstance(fee_tolerance, bool) or not isinstance(fee_tolerance, int) or fee_tolerance < 0:
        raise ValueError("fee_tolerance must be a non-negative integer")
    if len(inputs) + len(outputs) > max_coins:
        raise ValueError("fee-tolerant baseline exceeds max_coins")
    observed_fee = sum(inputs) - sum(outputs)
    if observed_fee < 0 or observed_fee > fee_tolerance:
        return ()

    mappings = set()
    for in_blocks in _partitions(list(range(len(inputs)))):
        for out_blocks in _partitions(list(range(len(outputs)))):
            if len(in_blocks) != len(out_blocks):
                continue
            in_sums = [sum(inputs[i] for i in block) for block in in_blocks]
            for permuted_outputs in permutations(out_blocks):
                out_sums = [sum(outputs[j] for j in block) for block in permuted_outputs]
                if all(left >= right for left, right in zip(in_sums, out_sums)):
                    mappings.add(_canonical(tuple(zip(in_blocks, permuted_outputs))))
    return tuple(sorted(mappings, key=lambda mapping: mapping.blocks))


def link_analysis(inputs, outputs, *, max_coins=12, balance_model="exact", fee_tolerance=0):
    """Compute uniform input-output link probabilities for the exact baseline.

    A link is present when an input and output share a sub-transaction block.
    This is Maurer's ``p_IO`` over the *full* mapping family, which is how §4.1
    defines it; the paper's own evaluation in §4.3 instead restricts to the
    non-derived family, for which see ``oracle_audit.exact_finest_link_matrix``.

    Equal mass per mapping is a modelling choice, not a measurement.  It is the
    choice that makes the resulting entropy largest, and a non-uniform posterior
    over the same family would leave less privacy than these numbers show.
    """
    inputs, outputs = tuple(inputs), tuple(outputs)
    observed_fee = sum(inputs) - sum(outputs)
    if balance_model == "exact":
        if fee_tolerance != 0:
            raise ValueError("fee_tolerance applies only to balance_model='fee_tolerant'")
        mappings = exact_subtransaction_mappings(inputs, outputs, max_coins=max_coins)
    elif balance_model == "fee_tolerant":
        mappings = fee_tolerant_subtransaction_mappings(
            inputs, outputs, fee_tolerance=fee_tolerance, max_coins=max_coins
        )
    else:
        raise ValueError("balance_model must be 'exact' or 'fee_tolerant'")
    if not mappings:
        return ExactLinkAnalysis((), (), 0.0, (), balance_model, observed_fee, fee_tolerance)

    counts = _link_counts(mappings, len(inputs), len(outputs))
    total = len(mappings)
    matrix = tuple(tuple(count / total for count in row) for row in counts)
    deterministic = tuple(
        (i, j)
        for i, row in enumerate(matrix)
        for j, probability in enumerate(row)
        if probability == 1.0
    )
    return ExactLinkAnalysis(mappings, matrix, log2(total), deterministic,
                             balance_model, observed_fee, fee_tolerance)


def _same_block_counts(mappings, size, side):
    counts = [[0] * size for _ in range(size)]
    for mapping in mappings:
        for blocks in mapping.blocks:
            for first in blocks[side]:
                for second in blocks[side]:
                    counts[first][second] += 1
    return tuple(tuple(row) for row in counts)


def same_block_probabilities(inputs, outputs, *, max_coins=12, balance_model="exact",
                             fee_tolerance=0):
    """Compute Maurer's ``p_II`` and ``p_OO`` over the family ``link_analysis`` uses.

    Two coins on the same side are linked when one block holds both.  ``p_II`` is
    the quantity the common-input-ownership heuristic asserts and the one the
    paper states its own conclusion in, so ``p_IO`` alone does not cover the
    paper's metrics.  Diagonal entries are 1.0 whenever a mapping exists, since a
    coin always shares its own block.
    """
    inputs, outputs = tuple(inputs), tuple(outputs)
    analysis = link_analysis(inputs, outputs, max_coins=max_coins,
                             balance_model=balance_model, fee_tolerance=fee_tolerance)
    total = len(analysis.mappings)
    if not total:
        return SameBlockAnalysis(0, (), (), balance_model, analysis.observed_fee,
                                 fee_tolerance)

    def matrix(size, side):
        return tuple(
            tuple(count / total for count in row)
            for row in _same_block_counts(analysis.mappings, size, side)
        )

    return SameBlockAnalysis(total, matrix(len(inputs), 0), matrix(len(outputs), 1),
                             balance_model, analysis.observed_fee, fee_tolerance)


def exact_link_analysis(inputs, outputs, *, max_coins=12):
    """Compatibility entry point restricted to exact conservation."""
    return link_analysis(inputs, outputs, max_coins=max_coins)


def fee_tolerant_link_analysis(inputs, outputs, *, fee_tolerance, max_coins=12):
    """Link analysis under explicit non-negative fee allocation."""
    return link_analysis(inputs, outputs, max_coins=max_coins,
                         balance_model="fee_tolerant", fee_tolerance=fee_tolerance)


def per_coin_link_evidence(inputs, outputs, *, max_coins=12, balance_model="exact",
                           fee_tolerance=0):
    """Expose per-coin marginals from the exact link matrix without scoring.

    An absent exact mapping is represented explicitly by zero candidates and
    ``max_link_probability=None``.  In particular, fees are not silently
    balanced or tolerated by this reference baseline.
    """
    inputs, outputs = tuple(inputs), tuple(outputs)
    analysis = link_analysis(inputs, outputs, max_coins=max_coins,
                             balance_model=balance_model, fee_tolerance=fee_tolerance)
    total = len(analysis.mappings)

    def evidence(role, values, rows):
        coins = []
        for index, (value, row) in enumerate(zip(values, rows)):
            candidates = tuple(
                ExactLinkCandidate(counterpart_index, count, count / total)
                for counterpart_index, count in enumerate(row)
                if count
            ) if total else ()
            coins.append(ExactCoinLinkEvidence(
                role=role,
                index=index,
                value=value,
                mapping_count=total,
                candidates=candidates,
                candidate_count=len(candidates),
                max_link_probability=max(
                    (candidate.probability for candidate in candidates),
                    default=None,
                ),
            ))
        return tuple(coins)

    if total:
        input_counts = _link_counts(analysis.mappings, len(inputs), len(outputs))
        output_counts = tuple(
            tuple(input_counts[i][j] for i in range(len(inputs)))
            for j in range(len(outputs))
        )
    else:
        input_counts = tuple(() for _ in inputs)
        output_counts = tuple(() for _ in outputs)

    return ExactPerCoinLinkAnalysis(
        mapping_count=total,
        inputs=evidence("input", inputs, input_counts),
        outputs=evidence("output", outputs, output_counts),
    )


def exact_per_coin_link_evidence(inputs, outputs, *, max_coins=12):
    """Compatibility entry point restricted to exact conservation."""
    return per_coin_link_evidence(inputs, outputs, max_coins=max_coins)
