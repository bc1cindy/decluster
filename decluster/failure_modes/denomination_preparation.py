"""Detect an overt fixed-denomination preparation shape before CoinJoin."""

from dataclasses import dataclass

from ..domain import (
    AttackReport,
    EvidenceChannel,
    EvidenceContext,
    Inconclusive,
    Subject,
    SubjectKind,
    TransactionFingerprintEvidence,
    TransactionFingerprintObserved,
)

RULE = "one exact-denomination output is consumed by the declared next CoinJoin"


@dataclass(frozen=True)
class DenominationPreparationObservation:
    transaction: Subject
    input_count: int
    output_amounts: tuple[int, ...]
    next_coinjoin_inputs: frozenset[int]
    denomination: int

    def __post_init__(self) -> None:
        if self.transaction.kind is not SubjectKind.TRANSACTION:
            raise ValueError("observation requires a transaction subject")
        if self.input_count < 1:
            raise ValueError("input_count must be positive")
        if not self.output_amounts or any(amount < 0 for amount in self.output_amounts):
            raise ValueError("output amounts must be non-empty and non-negative")
        if self.denomination <= 0:
            raise ValueError("denomination must be positive")
        if any(index < 0 or index >= len(self.output_amounts) for index in self.next_coinjoin_inputs):
            raise ValueError("next-CoinJoin output index is outside the transaction")


def paired_corpus() -> tuple[
    tuple[DenominationPreparationObservation, ...],
    tuple[DenominationPreparationObservation, ...],
]:
    denomination = 100_000
    preparations = tuple(
        DenominationPreparationObservation(
            Subject(SubjectKind.TRANSACTION, f"preparation-{index}"),
            2,
            (denomination, change),
            frozenset({0}),
            denomination,
        )
        for index, change in enumerate((17_000, 23_000, 41_000))
    )
    controls = tuple(
        DenominationPreparationObservation(
            Subject(SubjectKind.TRANSACTION, f"control-{index}"),
            2,
            (payment, change),
            frozenset({0}),
            denomination,
        )
        for index, (payment, change) in enumerate(
            ((93_000, 24_000), (107_000, 16_000), (88_000, 53_000))
        )
    )
    return preparations, controls


def fingerprint(observation: DenominationPreparationObservation) -> TransactionFingerprintEvidence:
    exact_outputs = tuple(
        index
        for index, amount in enumerate(observation.output_amounts)
        if amount == observation.denomination
    )
    exact_spent_next = sum(
        index in observation.next_coinjoin_inputs for index in exact_outputs
    )
    context = EvidenceContext(
        adversary="external on-chain observer",
        observables=(
            "predecessor input and output counts",
            "output amounts",
            "outputs consumed by the declared next CoinJoin",
        ),
        hypothesis="a predecessor transaction visibly prepares the next CoinJoin denomination",
        algorithm="exact-denomination predecessor shape",
        dataset="deterministic synthetic preparation and arity-matched controls",
        limitations=(
            "the next CoinJoin and its denomination are supplied",
            "the rule does not establish whether the predecessor was unilateral",
        ),
    )
    return TransactionFingerprintEvidence(
        observation.transaction,
        (
            ("input_count", observation.input_count),
            ("output_count", len(observation.output_amounts)),
            ("exact_denomination_outputs", len(exact_outputs)),
            ("exact_denomination_outputs_spent_next", exact_spent_next),
        ),
        context,
    )


def evaluate(observation: DenominationPreparationObservation) -> AttackReport:
    evidence = fingerprint(observation)
    features = dict(evidence.features)
    matched = features["exact_denomination_outputs"] == 1 and features[
        "exact_denomination_outputs_spent_next"
    ] == 1
    outcome = (
        TransactionFingerprintObserved(evidence, RULE)
        if matched
        else Inconclusive(
            (observation.transaction,),
            "the declared denomination-preparation fingerprint was not observed",
        )
    )
    return AttackReport(
        identifier=f"ctp.denomination-preparation.{observation.transaction.identifier}",
        attack="fixed-denomination preparation fingerprint",
        subjects=(observation.transaction,),
        channels=(EvidenceChannel("transaction_shape", (evidence,)),),
        outcomes=(outcome,),
        limitations=(
            "deterministic synthetic corpus",
            "controls match transaction arity but not a real-world population distribution",
            "a fingerprint match is not proof of unilateral construction or common ownership",
            "the CTP qualification has no separately cited empirical experiment",
        ),
    )
