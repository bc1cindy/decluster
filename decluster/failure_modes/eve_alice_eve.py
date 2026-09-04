"""Eve–Alice–Eve narrowing by an adversarial counterparty."""

from dataclasses import dataclass

from ..baselines.candidate_set_intersection import intersect_candidate_sets
from ..domain import (
    AttackReport,
    CandidateNarrowing,
    CandidateSetEvidence,
    EvidenceChannel,
    EvidenceContext,
    Inconclusive,
    IntersectionEvidence,
    Subject,
    SubjectKind,
)


@dataclass(frozen=True)
class CounterpartyReturnScenario:
    """Deposited inputs and customers consistent with each known origin."""

    counterparty: Subject
    deposited_inputs: tuple[Subject, ...]
    candidate_customers: tuple[frozenset[Subject], ...]

    def __post_init__(self) -> None:
        if self.counterparty.kind is not SubjectKind.CLUSTER:
            raise ValueError("counterparty must be a cluster subject")
        if not self.deposited_inputs or len(self.deposited_inputs) != len(
            self.candidate_customers
        ):
            raise ValueError("each deposited input requires a candidate set")
        if len(set(self.deposited_inputs)) != len(self.deposited_inputs):
            raise ValueError("deposited inputs must be distinct")
        if any(item.kind is not SubjectKind.OUTPOINT for item in self.deposited_inputs):
            raise ValueError("deposited inputs must be outpoint subjects")
        if any(len(candidates) < 2 for candidates in self.candidate_customers):
            raise ValueError("each input must remain ambiguous before intersection")


def ctp_consolidation_example() -> CounterpartyReturnScenario:
    """Return two independently mixed descendants consistent only with Alice."""
    alice = Subject(SubjectKind.CLUSTER, "alice")
    return CounterpartyReturnScenario(
        counterparty=Subject(SubjectKind.CLUSTER, "eve-atm"),
        deposited_inputs=(
            Subject(SubjectKind.OUTPOINT, ("coinjoin-1", 0)),
            Subject(SubjectKind.OUTPOINT, ("coinjoin-2", 0)),
        ),
        candidate_customers=(
            frozenset({alice, Subject(SubjectKind.CLUSTER, "bob")}),
            frozenset({alice, Subject(SubjectKind.CLUSTER, "carol")}),
        ),
    )


def evaluate(scenario: CounterpartyReturnScenario) -> AttackReport:
    """Evaluate candidate narrowing available to the known-origin counterparty."""
    provenance_context = EvidenceContext(
        adversary="counterparty with private transaction records",
        observables=(
            "dispensed outpoints",
            "descendant deposits",
            "CoinJoin ancestry",
        ),
        hypothesis="a deposited input belongs to one customer consistent with its ancestry",
        algorithm="known-origin candidate construction",
        dataset="ctp synthetic Eve-Alice-Eve fixture",
        limitations=("candidate customers are supplied by the fixture",),
    )
    candidates = tuple(
        CandidateSetEvidence(deposit, customers, provenance_context)
        for deposit, customers in zip(
            scenario.deposited_inputs, scenario.candidate_customers
        )
    )
    subjects = (scenario.counterparty,) + scenario.deposited_inputs
    if len(scenario.deposited_inputs) == 1:
        return AttackReport(
            identifier="ctp.eve-alice-eve",
            attack="known-origin counterparty return analysis",
            subjects=subjects,
            channels=(EvidenceChannel("known_origin_candidates", candidates),),
            outcomes=(
                Inconclusive(
                    subjects=scenario.deposited_inputs,
                    reason="one ambiguous return does not identify its customer",
                ),
            ),
            limitations=(
                "synthetic fixture",
                "behavioral priors and temporal patterns are not modeled",
                "candidate ancestry does not prove possession",
            ),
        )

    surviving = frozenset(
        intersect_candidate_sets(scenario.candidate_customers).surviving
    )
    intersection_context = EvidenceContext(
        adversary="counterparty with private transaction records",
        observables=("known origins", "multiple inputs in one deposit"),
        hypothesis="the consolidated deposited inputs share a customer",
        algorithm="known-origin candidate intersection",
        dataset="ctp synthetic Eve-Alice-Eve fixture",
        limitations=("common ownership of the deposited inputs is required",),
    )
    intersection = IntersectionEvidence(
        observations=scenario.deposited_inputs,
        candidates_before=min(map(len, scenario.candidate_customers)),
        candidates_after=surviving,
        context=intersection_context,
    )
    outcome = (
        CandidateNarrowing(intersection)
        if surviving
        else Inconclusive(subjects, "known-origin candidate sets do not overlap")
    )
    return AttackReport(
        identifier="ctp.eve-alice-eve",
        attack="known-origin counterparty return intersection",
        subjects=subjects,
        channels=(
            EvidenceChannel("known_origin_candidates", candidates),
            EvidenceChannel("return_intersection", (intersection,)),
        ),
        outcomes=(outcome,),
        limitations=(
            "synthetic fixture",
            "behavioral priors and temporal patterns are not modeled",
            "candidate narrowing is not identity attribution",
            "a collaborative deposit invalidates the common-ownership premise",
        ),
    )
