"""Retroactive narrowing after outputs from separate CoinJoins are co-spent."""

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
class ConsolidationScenario:
    """Two independently ambiguous outputs and their observed consolidation."""

    outputs: tuple[Subject, Subject]
    candidate_sets: tuple[frozenset[Subject], frozenset[Subject]]

    def __post_init__(self) -> None:
        if self.outputs[0] == self.outputs[1]:
            raise ValueError("consolidation requires distinct outputs")
        if any(len(candidates) < 2 for candidates in self.candidate_sets):
            raise ValueError("each output must be ambiguous before consolidation")


def ctp_example() -> ConsolidationScenario:
    """Return the minimal CTP-style case whose candidate sets overlap at Alice."""
    alice = Subject(SubjectKind.CLUSTER, "alice")
    return ConsolidationScenario(
        outputs=(
            Subject(SubjectKind.OUTPOINT, ("coinjoin-1", 0)),
            Subject(SubjectKind.OUTPOINT, ("coinjoin-2", 0)),
        ),
        candidate_sets=(
            frozenset({
                alice,
                Subject(SubjectKind.CLUSTER, "bob"),
                Subject(SubjectKind.CLUSTER, "carol"),
            }),
            frozenset({
                alice,
                Subject(SubjectKind.CLUSTER, "dave"),
                Subject(SubjectKind.CLUSTER, "erin"),
            }),
        ),
    )


def evaluate(scenario: ConsolidationScenario) -> AttackReport:
    """Evaluate narrowing conditional on treating the consolidation as co-ownership."""
    candidate_context = EvidenceContext(
        adversary="external on-chain observer",
        observables=("pre-CoinJoin clusters", "equal-output CoinJoin membership"),
        hypothesis="each post-CoinJoin output has one of its candidate origin clusters",
        algorithm="candidate origin construction",
        dataset="ctp synthetic consolidation fixture",
        limitations=("candidate sets are supplied by the fixture",),
    )
    candidates = tuple(
        CandidateSetEvidence(output, origins, candidate_context)
        for output, origins in zip(scenario.outputs, scenario.candidate_sets)
    )

    result = intersect_candidate_sets(scenario.candidate_sets)
    intersection_context = EvidenceContext(
        adversary="external on-chain observer",
        observables=("candidate origin clusters", "later co-spend"),
        hypothesis="the co-spent outputs share an owner and therefore an origin cluster",
        algorithm="candidate set intersection",
        dataset="ctp synthetic consolidation fixture",
        limitations=(
            "narrowing is conditional on the later co-spend being a valid ownership link",
        ),
    )
    intersection = IntersectionEvidence(
        observations=scenario.outputs,
        candidates_before=min(map(len, scenario.candidate_sets)),
        candidates_after=frozenset(result.surviving),
        context=intersection_context,
    )
    outcome = (
        CandidateNarrowing(intersection)
        if intersection.candidates_after
        else NoSharedCandidates(intersection)
    )
    return AttackReport(
        identifier="ctp.equal-output-consolidation",
        attack="retroactive candidate-set intersection after consolidation",
        subjects=scenario.outputs,
        channels=(
            EvidenceChannel("candidate_origins", candidates),
            EvidenceChannel("consolidation_intersection", (intersection,)),
        ),
        outcomes=(outcome,),
        limitations=(
            "synthetic fixture",
            "the report demonstrates conditional narrowing, not an identity",
            "a collaborative consolidation would invalidate the co-ownership premise",
        ),
    )
