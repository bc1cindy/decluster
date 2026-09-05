"""Show why a positive unnecessary-input predicate does not identify PayJoin."""

from dataclasses import dataclass
from enum import Enum

from ..baselines.unnecessary_input import UIHStatus, analyze_blockstream
from ..domain import (
    AttackReport,
    EvidenceChannel,
    EvidenceContext,
    Inconclusive,
    Subject,
    SubjectKind,
    UnnecessaryInputEvidence,
)


class LatentTransactionForm(str, Enum):
    """Possible worlds that can share the same on-chain amount observation."""

    ORDINARY_CONSOLIDATION = "ordinary_single_owner_consolidation"
    TWO_PARTY_PAYJOIN = "two_party_payjoin"
    NS1R = "many_senders_one_receiver"
    NSNR = "many_senders_many_receivers"
    NET_SETTLEMENT = "net_settlement_with_cycles"


@dataclass(frozen=True)
class UnnecessaryInputScenario:
    transaction: Subject
    inputs: tuple[int, ...]
    outputs: tuple[int, int]
    possible_forms: tuple[LatentTransactionForm, ...]

    def __post_init__(self) -> None:
        if self.transaction.kind is not SubjectKind.TRANSACTION:
            raise ValueError("scenario requires a transaction subject")
        if len(self.inputs) < 2:
            raise ValueError("scenario requires at least two inputs")
        if len(set(self.possible_forms)) < 2:
            raise ValueError("scenario requires at least two distinct latent forms")


def observationally_equivalent_example() -> UnnecessaryInputScenario:
    """One amount vector compatible with unilateral and collaborative worlds."""

    return UnnecessaryInputScenario(
        transaction=Subject(SubjectKind.TRANSACTION, "uih-equivalent-worlds"),
        inputs=(600, 600, 600),
        outputs=(1_000, 700),
        possible_forms=(
            LatentTransactionForm.ORDINARY_CONSOLIDATION,
            LatentTransactionForm.TWO_PARTY_PAYJOIN,
            LatentTransactionForm.NET_SETTLEMENT,
        ),
    )


def evaluate(scenario: UnnecessaryInputScenario) -> AttackReport:
    """Classify the amounts while refusing any latent-form or ownership conclusion."""

    analysis = analyze_blockstream(scenario.inputs, scenario.outputs)
    if analysis.status not in {UIHStatus.UIH1, UIHStatus.UIH2}:
        raise ValueError("failure-mode scenario must have a valid UIH classification")
    if analysis.fee is None or analysis.removed_input_index is None:
        raise RuntimeError("valid UIH analysis omitted its fee or input witness")

    forms = tuple(form.value for form in scenario.possible_forms)
    context = EvidenceContext(
        adversary="external observer with transaction amounts and no participant labels",
        observables=("input amounts", "output amounts", "transaction fee"),
        hypothesis="a proper input subset can fund an output and the observed fee",
        algorithm="Ghesmati et al. Algorithm 2 BlockStream UIH1/UIH2",
        dataset="deterministic observational-equivalence fixture",
        limitations=(
            "the same observation is compatible with " + ", ".join(forms),
            "gross obligations and cycles are not observable from net transaction amounts",
        ),
    )
    evidence = UnnecessaryInputEvidence(
        transaction=scenario.transaction,
        definition="blockstream_fee_aware",
        classification=analysis.status.value,
        fee=analysis.fee,
        removed_input_index=analysis.removed_input_index,
        context=context,
    )
    return AttackReport(
        identifier=f"ctp.unnecessary-input.{scenario.transaction.identifier}",
        attack="unnecessary-input observational equivalence",
        subjects=(scenario.transaction,),
        channels=(EvidenceChannel("unnecessary_input_shape", (evidence,)),),
        outcomes=(
            Inconclusive(
                (scenario.transaction,),
                "UIH does not distinguish the declared latent transaction forms",
            ),
        ),
        limitations=(
            "a positive predicate does not identify PayJoin",
            "no participant role, ownership relation, payment output, or gross payment is inferred",
            "ordinary consolidation and collaborative settlement share the same observable",
            "the fixture demonstrates non-identifiability, not real-world prevalence",
        ),
    )
