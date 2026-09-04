"""Paired scenarios where equal point entropy has different longitudinal outcomes."""

from dataclasses import dataclass
from math import isfinite, log2

from ..domain import (
    AttackReport,
    CandidateNarrowing,
    EvidenceChannel,
    EvidenceContext,
    IntersectionEvidence,
    ProvenanceDistributionEvidence,
    Subject,
    SubjectKind,
)


@dataclass(frozen=True)
class EntropyScenario:
    identifier: str
    target: Subject
    probabilities: tuple[tuple[Subject, float], ...]
    observations: tuple[tuple[Subject, frozenset[Subject]], ...]

    def __post_init__(self) -> None:
        if not self.identifier:
            raise ValueError("scenario identifier must not be empty")
        if self.target.kind is not SubjectKind.OUTPOINT:
            raise ValueError("target must be an outpoint")
        if len(self.observations) < 2:
            raise ValueError("longitudinal comparison requires at least two observations")
        candidates = {candidate for candidate, _ in self.probabilities}
        if not candidates or len(candidates) != len(self.probabilities):
            raise ValueError("initial distribution must not be empty")
        probabilities = tuple(probability for _, probability in self.probabilities)
        if any(not isfinite(probability) or probability < 0.0 for probability in probabilities):
            raise ValueError("posterior probabilities must be finite and non-negative")
        if abs(sum(probabilities) - 1.0) > 1e-9:
            raise ValueError("posterior probabilities must sum to one")
        if any(not observed or not observed <= candidates for _, observed in self.observations):
            raise ValueError("observed candidate sets must be non-empty subsets of the posterior")

    @property
    def entropy_bits(self) -> float:
        return -sum(
            probability * log2(probability)
            for _, probability in self.probabilities
            if probability > 0.0
        )


def _candidate(identifier: str) -> Subject:
    return Subject(SubjectKind.CLUSTER, identifier)


def paired_examples() -> tuple[EntropyScenario, EntropyScenario]:
    candidates = tuple(_candidate(identifier) for identifier in ("a", "b", "c", "d"))
    probabilities = tuple((candidate, 0.25) for candidate in candidates)
    brittle = EntropyScenario(
        identifier="brittle-overlap",
        target=Subject(SubjectKind.OUTPOINT, ("brittle", 0)),
        probabilities=probabilities,
        observations=(
            (Subject(SubjectKind.COIN, "brittle-observation-1"), frozenset(candidates[:2])),
            (
                Subject(SubjectKind.COIN, "brittle-observation-2"),
                frozenset((candidates[0], candidates[2])),
            ),
        ),
    )
    robust = EntropyScenario(
        identifier="overlapping-crowd",
        target=Subject(SubjectKind.OUTPOINT, ("overlapping", 0)),
        probabilities=probabilities,
        observations=(
            (Subject(SubjectKind.COIN, "overlapping-observation-1"), frozenset(candidates[:3])),
            (
                Subject(SubjectKind.COIN, "overlapping-observation-2"),
                frozenset((candidates[0], candidates[1], candidates[3])),
            ),
        ),
    )
    return brittle, robust


def evaluate(scenario: EntropyScenario) -> AttackReport:
    context = EvidenceContext(
        adversary="observer who links multiple post-CoinJoin observations",
        observables=("initial candidate posterior", "candidate sets after later observations"),
        hypothesis="point entropy alone predicts resistance to longitudinal intersection",
        algorithm="explicit posterior entropy followed by candidate-set intersection",
        dataset="CTP synthetic equal-entropy counterexample",
        limitations=("posterior probabilities and later candidate sets are supplied",),
    )
    posterior = ProvenanceDistributionEvidence(
        scenario.target, scenario.probabilities, context
    )
    survivors = frozenset.intersection(
        *(candidates for _, candidates in scenario.observations)
    )
    intersection = IntersectionEvidence(
        tuple(observation for observation, _ in scenario.observations),
        len(scenario.probabilities),
        survivors,
        context,
    )
    return AttackReport(
        identifier=f"ctp.entropy-insufficiency.{scenario.identifier}",
        attack="longitudinal intersection after an equal-entropy posterior",
        subjects=(scenario.target,) + tuple(candidate for candidate, _ in scenario.probabilities),
        channels=(
            EvidenceChannel("initial_posterior", (posterior,)),
            EvidenceChannel("longitudinal_intersection", (intersection,)),
        ),
        outcomes=(CandidateNarrowing(intersection),),
        limitations=(
            "synthetic counterexample",
            "equal point entropy does not imply equal future candidate-set overlap",
            "the fixture falsifies sufficiency but does not estimate real-world attack frequency",
            "the result is not a privacy score or certificate",
        ),
    )
