"""Unnecessary-input classifications from Ghesmati et al. §3.

The published comparison is scoped to transactions with more than one input
and exactly two outputs.  A positive classification describes transaction
shape.  It does not identify PayJoin, ownership, or the payment output.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any


MAX_AMOUNT = 2**64 - 1


class UIHStatus(str, Enum):
    """Outcome of the fee-aware BlockStream classification."""

    UIH1 = "uih1"
    UIH2 = "uih2"
    OUT_OF_SCOPE = "out_of_scope"
    INVALID = "invalid"


@dataclass(frozen=True)
class UIHAnalysis:
    """A model-relative UIH result with the values needed to audit it."""

    status: UIHStatus
    fee: int | None = None
    removed_input_index: int | None = None
    change_output_index: int | None = None
    reason: str | None = None


def _valid_amounts(values: Sequence[int]) -> bool:
    return all(type(value) is int and 0 < value <= MAX_AMOUNT for value in values)


def analyze_blockstream(inputs: Sequence[int], outputs: Sequence[int]) -> UIHAnalysis:
    """Apply Algorithm 2 of Ghesmati et al. to a two-output transaction.

    UIH2 holds when removing one occurrence of the smallest input still leaves
    enough value to fund the largest output and the observed transaction fee.
    UIH1 holds when the analogous test succeeds only for the smaller output.
    For a valid, value-conserving two-output transaction these cases partition
    the paper's domain.  Ties between smallest inputs use the first index only
    to make the witness deterministic.
    """

    if len(inputs) < 2 or len(outputs) != 2:
        return UIHAnalysis(
            UIHStatus.OUT_OF_SCOPE,
            reason="requires at least two inputs and exactly two outputs",
        )
    if not _valid_amounts(inputs) or not _valid_amounts(outputs):
        return UIHAnalysis(
            UIHStatus.INVALID,
            reason="amounts must be positive unsigned 64-bit integers",
        )

    total_in = sum(inputs)
    total_out = sum(outputs)
    if total_in > MAX_AMOUNT or total_out > MAX_AMOUNT:
        return UIHAnalysis(UIHStatus.INVALID, reason="amount sum exceeds unsigned 64-bit range")
    fee = total_in - total_out
    if fee < 0:
        return UIHAnalysis(UIHStatus.INVALID, reason="outputs exceed inputs")

    removed_index = min(range(len(inputs)), key=inputs.__getitem__)
    remaining = total_in - inputs[removed_index]
    smaller_index = (
        0
        if outputs[0] < outputs[1]
        else 1
        if outputs[1] < outputs[0]
        else None
    )
    if remaining >= max(outputs) + fee:
        return UIHAnalysis(UIHStatus.UIH2, fee=fee, removed_input_index=removed_index)
    return UIHAnalysis(
        UIHStatus.UIH1,
        fee=fee,
        removed_input_index=removed_index,
        change_output_index=smaller_index,
        reason=None if smaller_index is not None else "equal outputs prevent change attribution",
    )


def blocksci_uih1(inputs: Sequence[int], outputs: Sequence[int]) -> bool | None:
    """Return BlockSci's strict optimal-change predicate, or ``None`` out of scope."""

    if (
        len(inputs) < 2
        or len(outputs) != 2
        or not _valid_amounts(inputs)
        or not _valid_amounts(outputs)
    ):
        return None
    return min(outputs) < min(inputs)


def gibson_flags(inputs: Sequence[int], outputs: Sequence[int]) -> tuple[bool, bool] | None:
    """Return the independent UIH1/UIH2 flags from Algorithm 3.

    This older UIH2 predicate is intentionally strict and can miss cases where
    several retained inputs jointly fund the largest output.
    """

    if (
        len(inputs) < 2
        or len(outputs) != 2
        or not _valid_amounts(inputs)
        or not _valid_amounts(outputs)
    ):
        return None
    return min(outputs) < min(inputs), max(inputs) > max(outputs)


def analyze_transaction(transaction: Mapping[str, Any]) -> UIHAnalysis:
    """Extract values from the project's transaction shape and run Algorithm 2.

    Missing values remain an explicit invalid result.  This adapter performs no
    ownership inference and deliberately does not fall back to another UIH
    definition.
    """

    try:
        vin: Sequence[Mapping[str, Any]] = transaction["vin"]
        vout: Sequence[Mapping[str, Any]] = transaction["vout"]
        inputs = [item.get("prevout", {}).get("value", item.get("value")) for item in vin]
        outputs = [item.get("value") for item in vout]
    except (AttributeError, KeyError, TypeError):
        return UIHAnalysis(UIHStatus.INVALID, reason="malformed transaction structure")
    if any(value is None for value in inputs + outputs):
        return UIHAnalysis(UIHStatus.INVALID, reason="transaction amounts are incomplete")
    return analyze_blockstream(inputs, outputs)
