"""Retroactive linkage of payments when their change outputs are consolidated."""

from dataclasses import dataclass

from ..baselines.candidate_set_intersection import intersect_candidate_sets
from ..domain import (
    AttackReport,
    CandidateNarrowing,
    CandidateSetEvidence,
    EvidenceChannel,
    EvidenceContext,
    IntersectionEvidence,
    NoSharedCandidates,
    Subject,
    SubjectKind,
)


@dataclass(frozen=True)
class ChangeConsolidationScenario:
    """Two prior payments whose candidate change outputs are later co-spent."""

    payments: tuple[Subject, Subject]
    change_outputs: tuple[Subject, Subject]
    candidate_owners: tuple[frozenset[Subject], frozenset[Subject]]

    def __post_init__(self) -> None:
        if len(set(self.payments)) != 2 or len(set(self.change_outputs)) != 2:
            raise ValueError("payments and change outputs must be distinct")
        if any(
            payment.kind is not SubjectKind.TRANSACTION for payment in self.payments
        ):
            raise ValueError("payments must be transaction subjects")
        if any(
            output.kind is not SubjectKind.OUTPOINT for output in self.change_outputs
        ):
            raise ValueError("change outputs must be outpoint subjects")
        if any(len(owners) < 2 for owners in self.candidate_owners):
            raise ValueError("each candidate change output must remain ambiguous")


def ctp_example() -> ChangeConsolidationScenario:
    """Return the CTP-style case where Alice's two changes meet later."""
    alice = Subject(SubjectKind.CLUSTER, "alice")
    return ChangeConsolidationScenario(
        payments=(
            Subject(SubjectKind.TRANSACTION, "payment-1"),
            Subject(SubjectKind.TRANSACTION, "payment-2"),
        ),
        change_outputs=(
            Subject(SubjectKind.OUTPOINT, ("payment-1", 1)),
            Subject(SubjectKind.OUTPOINT, ("payment-2", 1)),
        ),
        candidate_owners=(
            frozenset({alice, Subject(SubjectKind.CLUSTER, "bob")}),
            frozenset({alice, Subject(SubjectKind.CLUSTER, "carol")}),
        ),
    )


def evaluate(scenario: ChangeConsolidationScenario) -> AttackReport:
    """Evaluate retroactive linkage conditional on change identification and CIOH."""
    candidate_context = EvidenceContext(
        adversary="external on-chain observer",
        observables=("payment transactions", "candidate change outputs"),
        hypothesis="each selected output is change owned by one candidate cluster",
        algorithm="change-candidate construction",
        dataset="ctp synthetic change-consolidation fixture",
        limitations=("change identification is supplied by the fixture",),
    )
    candidates = tuple(
        CandidateSetEvidence(output, owners, candidate_context)
        for output, owners in zip(scenario.change_outputs, scenario.candidate_owners)
    )
    surviving = frozenset(
        intersect_candidate_sets(scenario.candidate_owners).surviving
    )
    intersection_context = EvidenceContext(
        adversary="external on-chain observer",
        observables=("candidate change outputs", "later co-spend"),
        hypothesis="identified change outputs in the co-spend share an owner",
        algorithm="candidate-owner intersection",
        dataset="ctp synthetic change-consolidation fixture",
        limitations=(
            "the inference requires both change identifications and the co-spend "
            "ownership premise",
        ),
    )
    intersection = IntersectionEvidence(
        observations=scenario.payments,
        candidates_before=min(map(len, scenario.candidate_owners)),
        candidates_after=surviving,
        context=intersection_context,
    )
    outcome = (
        CandidateNarrowing(intersection)
        if surviving
        else NoSharedCandidates(intersection)
    )
    return AttackReport(
        identifier="ctp.change-consolidation",
        attack="retroactive payment linkage through consolidated change",
        subjects=scenario.payments + scenario.change_outputs,
        channels=(
            EvidenceChannel("change_candidates", candidates),
            EvidenceChannel("payment_intersection", (intersection,)),
        ),
        outcomes=(outcome,),
        limitations=(
            "synthetic fixture",
            "the report narrows candidate owners and does not identify a real person",
            "a collaborative co-spend invalidates the common-ownership premise",
        ),
    )
