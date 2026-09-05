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


@dataclass(frozen=True)
class FormObservation:
    """A collaborative form and the amounts visible to an external observer."""

    form: LatentTransactionForm
    inputs: tuple[int, ...]
    outputs: tuple[int, ...]


@dataclass(frozen=True)
class Obligation:
    payer: str
    receiver: str
    amount: int

    def __post_init__(self) -> None:
        if not self.payer or not self.receiver or self.payer == self.receiver:
            raise ValueError("obligation requires distinct named parties")
        if self.amount <= 0:
            raise ValueError("obligation amount must be positive")


def net_balances(obligations: tuple[Obligation, ...]) -> dict[str, int]:
    """Return received minus sent for each participant."""

    balances: dict[str, int] = {}
    for obligation in obligations:
        balances.setdefault(obligation.payer, 0)
        balances.setdefault(obligation.receiver, 0)
        balances[obligation.payer] -= obligation.amount
        balances[obligation.receiver] += obligation.amount
    return dict(sorted(balances.items()))


def collaborative_form_examples() -> tuple[FormObservation, FormObservation]:
    """CTP-style NS1R and NSNR shapes outside the paper's two-output scope."""

    return (
        FormObservation(
            LatentTransactionForm.NS1R,
            (40, 50, 60, 90),
            (160, 30, 30, 20),
        ),
        FormObservation(
            LatentTransactionForm.NSNR,
            (90, 15, 40, 30, 45, 35),
            (85, 25, 50, 40, 45, 10),
        ),
    )


def cycle_equivalent_obligations() -> tuple[
    tuple[Obligation, ...], tuple[Obligation, ...]
]:
    """Two gross obligation graphs with identical observable net balances."""

    simple = (Obligation("alice", "bob", 500),)
    with_cycle = (
        Obligation("alice", "bob", 800),
        Obligation("bob", "carol", 300),
        Obligation("carol", "alice", 300),
    )
    return simple, with_cycle


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
