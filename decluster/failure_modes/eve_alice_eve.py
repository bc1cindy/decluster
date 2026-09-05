"""Eve–Alice–Eve narrowing by an adversarial counterparty.

The writeup's claim about this adversary is not that a second consolidated return adds a
candidate's worth of information, but that the loss compounds. One intersection cannot show
that, so `ctp_compounding_example` supplies three returns and a stated candidate universe, and
the report then carries the two numbers that separate the readings: the bits the successive
intersections accumulate, and the bits striking one candidate off the list per return would
have yielded over the same returns. Both are properties of the fixture. Neither is a measured
shrink rate, and no rate is assumed to obtain them.
"""

import math
from dataclasses import dataclass
from typing import Optional

from ..baselines.candidate_set_intersection import intersect_candidate_sets
from ..domain import (
    AttackReport,
    CandidateNarrowing,
    CandidateSetEvidence,
    EvidenceChannel,
    EvidenceContext,
    ExperimentalComposition,
    Inconclusive,
    IntersectionEvidence,
    Subject,
    SubjectKind,
)
from ..intersect import accumulate_intersections


@dataclass(frozen=True)
class CounterpartyReturnScenario:
    """Deposited inputs and customers consistent with each known origin."""

    counterparty: Subject
    deposited_inputs: tuple[Subject, ...]
    candidate_customers: tuple[frozenset[Subject], ...]
    universe_size: Optional[int] = None

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
        if self.universe_size is not None:
            widest = max(len(candidates) for candidates in self.candidate_customers)
            if isinstance(self.universe_size, bool) or not isinstance(self.universe_size, int):
                raise ValueError("universe size must be an integer")
            if self.universe_size < widest:
                raise ValueError("universe size must cover the widest candidate set")


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


def ctp_compounding_example() -> CounterpartyReturnScenario:
    """Three returns against a stated customer universe, so the accumulation is measurable.

    Two returns show the intersection; they do not distinguish compounding from adding up.
    Separating those readings needs more than one intersection and a universe to measure the
    narrowing against, which is what this scenario supplies and `ctp_consolidation_example`
    deliberately does not.
    """
    alice = Subject(SubjectKind.CLUSTER, "alice")
    bob = Subject(SubjectKind.CLUSTER, "bob")
    carol = Subject(SubjectKind.CLUSTER, "carol")
    dave = Subject(SubjectKind.CLUSTER, "dave")
    return CounterpartyReturnScenario(
        counterparty=Subject(SubjectKind.CLUSTER, "eve-atm"),
        deposited_inputs=(
            Subject(SubjectKind.OUTPOINT, ("coinjoin-1", 0)),
            Subject(SubjectKind.OUTPOINT, ("coinjoin-2", 0)),
            Subject(SubjectKind.OUTPOINT, ("coinjoin-3", 0)),
        ),
        candidate_customers=(
            frozenset({alice, bob, carol}),
            frozenset({alice, carol, dave}),
            frozenset({alice, bob, dave}),
        ),
        universe_size=8,
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
        composition=_compounding(scenario),
    )


def accumulate(
    scenario: CounterpartyReturnScenario,
) -> tuple[frozenset[Subject], float]:
    """Survivors and accumulated bits over the returns, in order. Requires `universe_size`."""
    survivors, bits = accumulate_intersections(
        [[{customer: 1.0 for customer in customers}]
         for customers in scenario.candidate_customers],
        universe_size=scenario.universe_size,
    )
    return frozenset(survivors), bits


def _elimination_baseline_bits(universe_size: int, returns: int) -> float:
    """Bits from striking one candidate off the list per return — the additive reading."""
    return math.log2(universe_size / max(universe_size - returns, 1))


def _compounding(
    scenario: CounterpartyReturnScenario,
) -> Optional[ExperimentalComposition]:
    """Accumulated narrowing against the one-at-a-time baseline, or None without a universe."""
    if scenario.universe_size is None:
        return None
    _survivors, bits = accumulate(scenario)
    additive = _elimination_baseline_bits(scenario.universe_size, len(scenario.deposited_inputs))
    return ExperimentalComposition(
        method="log2 narrowing accumulated across successive consolidated returns",
        channel_ids=("return_intersection",),
        value=bits,
        unit="bits",
        interpretation=(
            f"{bits:.2f} bits over {len(scenario.deposited_inputs)} returns against "
            f"{additive:.2f} for striking one candidate off a universe of "
            f"{scenario.universe_size} per return; the gap is what compounding means here, "
            "and it is a property of this fixture, not a measured rate"
        ),
    )
