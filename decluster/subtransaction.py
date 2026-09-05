"""Amount channel — sub-transaction re-partition of a 2-in/2-out merged transaction by the
roundness of the implied payment (an output minus the input it contributed). Primary only in the
*decidable* regime (a plausible round partition); silenced by dense or deliberately
underdetermined constructions, where the fingerprint and graph-topology channels carry the weight.
Refuse-only: it can cut a co-spend from the graph, never add a positive same-owner link. Roundness
is a heuristic, not proof. ("Structural" is reserved for the graph/provenance attack, not this.)"""
import math
from dataclasses import dataclass
from enum import Enum


class TransactionModel(str, Enum):
    """Assumptions under which amount interpretations may be consumed."""

    UNKNOWN = "unknown"
    RESTRICTED_TWO_PARTY_PAYMENT = "restricted_two_party_payment"
    NET_SETTLEMENT_ALLOWED = "net_settlement_allowed"


class AmountDecisionStatus(str, Enum):
    INCONCLUSIVE = "inconclusive"
    DIRECTIONAL_HYPOTHESIS = "directional_hypothesis"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass(frozen=True)
class AmountInterpretation:
    implied_net_transfer: int
    roundness_score: int
    receiver_input_index: int
    receiver_output_index: int


@dataclass(frozen=True)
class AmountModelDecision:
    status: AmountDecisionStatus
    model: TransactionModel
    interpretations: tuple[AmountInterpretation, ...]
    ranked: tuple[AmountInterpretation, ...]
    refuse: tuple[tuple[str, str], ...] = ()
    links: tuple[tuple[str, str], ...] = ()
    reason: str = ""

def roundness(x):
    """how 'designed' the number looks: +k if divisible by 10^k (1000 -> 3, 4750 -> 1)."""
    if x <= 0: return 0
    k = 0
    while x % 10 == 0:
        x //= 10; k += 1
    return k

def enumerate_amount_interpretations(tx):
    """Enumerate positive implied net transfers for every 2-in/2-out allocation."""
    ins = [(i, v["prevout"]["value"]) for i, v in enumerate(tx["vin"])]
    outs = [(j, o["value"]) for j, o in enumerate(tx["vout"])]
    if len(ins) != 2 or len(outs) != 2:
        return ()
    return tuple(
        AmountInterpretation(wr - vr, roundness(wr - vr), ri, ro)
        for ri, vr in ins
        for ro, wr in outs
        if wr - vr > 0
    )


def rank_amount_interpretations(interpretations):
    """Rank candidates by roundness and then magnitude without selecting truth."""
    return tuple(
        sorted(
            interpretations,
            key=lambda item: (-item.roundness_score, -item.implied_net_transfer),
        )
    )


def subtransactions(tx):
    """balanced 2-owner partitions of a 2-in/2-out merged transaction, ranked by plausibility.
    Returns (ranked, ambiguity_bits); ranked = [(payment, score, r_in_idx, r_out_idx)].
    `ambiguity_bits = log2(count)` is a raw *count* diagnostic (Boltzmann-style), NOT a privacy
    quantity — what bounds anonymity is the entropy of the *distribution* over partitions, not the
    count (paper §10). It is reported for transparency and never fed into clustering as anonymity."""
    interpretations = enumerate_amount_interpretations(tx)
    ranked = rank_amount_interpretations(interpretations)
    plausible = [
        (
            item.implied_net_transfer,
            item.roundness_score,
            item.receiver_input_index,
            item.receiver_output_index,
        )
        for item in ranked
    ]
    amb = math.log2(len(plausible)) if plausible else None
    return plausible, amb

def norm(t):
    """mempool.space tx -> shape subtransaction expects (prevout.value present)."""
    return {"txid": t["txid"],
            "vin": [{"txid": v["txid"], "prevout": {"value": v["prevout"]["value"]}} for v in t["vin"]],
            "vout": [{"value": o["value"]} for o in t["vout"]]}

def evaluate_amount_model(tx, model):
    """Evaluate ranked interpretations without exceeding the declared model.

    Unknown and net-settlement-capable models retain every candidate and never
    emit ownership-directional links or refusals.  The restricted model exposes
    the historical roundness hypothesis for compatibility; it remains a
    hypothesis rather than an observed payment.
    """
    if not isinstance(model, TransactionModel):
        raise TypeError("model must be a TransactionModel")
    interpretations = enumerate_amount_interpretations(tx)
    ranked = rank_amount_interpretations(interpretations)
    if not ranked:
        return AmountModelDecision(
            AmountDecisionStatus.OUT_OF_SCOPE,
            model,
            interpretations,
            ranked,
            reason="requires a positive interpretation in a 2-in/2-out transaction",
        )
    if model in {TransactionModel.UNKNOWN, TransactionModel.NET_SETTLEMENT_ALLOWED}:
        return AmountModelDecision(
            AmountDecisionStatus.INCONCLUSIVE,
            model,
            interpretations,
            ranked,
            reason="roundness cannot identify allocation when the transaction form is not restricted",
        )

    best = ranked[0]
    txids = tuple(v["txid"] for v in tx["vin"])
    sender_input = 1 - best.receiver_input_index
    sender_output = 1 - best.receiver_output_index
    return AmountModelDecision(
        AmountDecisionStatus.DIRECTIONAL_HYPOTHESIS,
        model,
        interpretations,
        ranked,
        refuse=((txids[sender_input], txids[best.receiver_input_index]),),
        links=(
            (txids[best.receiver_input_index], f"{tx['txid']}:{best.receiver_output_index}"),
            (txids[sender_input], f"{tx['txid']}:{sender_output}"),
        ),
        reason="highest-roundness implied net transfer under a restricted two-party model",
    )


def partition_signal(tx):
    """structural signal for the combiner: refuse (different-owner inputs) + link
    (input -> its output) from the most likely partition. scope guard -> empty."""
    decision = evaluate_amount_model(tx, TransactionModel.RESTRICTED_TWO_PARTY_PAYMENT)
    amb = math.log2(len(decision.interpretations)) if decision.interpretations else None
    if decision.status is not AmountDecisionStatus.DIRECTIONAL_HYPOTHESIS:
        return {"refuse": [], "link": [], "payment": None, "ambiguity_bits": amb}
    best = decision.ranked[0]
    return {
        "refuse": list(decision.refuse),
        # UNUSED by cluster_refined: amounts REFUSE only, never add a positive same-owner link
        # (sub-transaction evidence can cut a coin from the graph, never inflate the score). Kept
        # for diagnostics/tests; do not wire into clustering as a positive signal.
        "link": list(decision.links),
        "payment": best.implied_net_transfer,
        "ambiguity_bits": amb,                                      # count diagnostic, not privacy (see subtransactions)
    }
