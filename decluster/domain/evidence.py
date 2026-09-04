"""Closed evidence types for ownership attacks and partition refinement.

Evidence records observations and model outputs.  It does not itself authorize a
cluster merge, a refusal, or a split; those decisions are represented by outcome
types in :mod:`decluster.domain.outcome`.
"""

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Hashable, Optional, TypeAlias, Union


class SubjectKind(str, Enum):
    COIN = "coin"
    OUTPOINT = "outpoint"
    TRANSACTION = "transaction"
    CLUSTER = "cluster"
    MAPPING = "mapping"
    PARTITION = "partition"


@dataclass(frozen=True)
class Subject:
    kind: SubjectKind
    identifier: Hashable

    def __post_init__(self) -> None:
        if self.identifier is None or (
            isinstance(self.identifier, str) and not self.identifier
        ):
            raise ValueError("subject identifier must not be empty")
        try:
            hash(self.identifier)
        except TypeError as exc:
            raise ValueError("subject identifier must be hashable") from exc


class Direction(str, Enum):
    SUPPORTS_COMMON_OWNERSHIP = "supports_common_ownership"
    OPPOSES_COMMON_OWNERSHIP = "opposes_common_ownership"
    DESCRIPTIVE = "descriptive"


@dataclass(frozen=True)
class EvidenceContext:
    adversary: str
    observables: tuple[str, ...]
    hypothesis: str
    algorithm: str
    dataset: Optional[str] = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for label, value in (
            ("adversary", self.adversary),
            ("hypothesis", self.hypothesis),
            ("algorithm", self.algorithm),
        ):
            if not value:
                raise ValueError(f"{label} must not be empty")
        if not self.observables or any(not item for item in self.observables):
            raise ValueError("observables must contain non-empty values")
        if any(not item for item in self.limitations):
            raise ValueError("limitations must contain non-empty values")


def _require_pair(subject: Subject, target: Subject) -> None:
    if subject == target:
        raise ValueError("subject and target must be distinct")


def _require_finite(value: float, label: str) -> None:
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")


@dataclass(frozen=True)
class OwnershipLikelihoodEvidence:
    subject: Subject
    target: Subject
    log2_odds: float
    context: EvidenceContext
    direction: Direction

    def __post_init__(self) -> None:
        _require_pair(self.subject, self.target)
        _require_finite(self.log2_odds, "log2_odds")
        if self.direction is Direction.DESCRIPTIVE:
            raise ValueError("ownership likelihood must have an ownership direction")


@dataclass(frozen=True)
class CannotLinkEvidence:
    subject: Subject
    target: Subject
    context: EvidenceContext
    reason: str

    def __post_init__(self) -> None:
        _require_pair(self.subject, self.target)
        if not self.reason:
            raise ValueError("cannot-link reason must not be empty")


@dataclass(frozen=True)
class MappingEvidence:
    inputs: tuple[Subject, ...]
    outputs: tuple[Subject, ...]
    mapping_count: int
    context: EvidenceContext

    def __post_init__(self) -> None:
        if not self.inputs or not self.outputs:
            raise ValueError("mapping evidence requires inputs and outputs")
        if self.mapping_count < 0:
            raise ValueError("mapping_count must be non-negative")


@dataclass(frozen=True)
class CandidateSetEvidence:
    subject: Subject
    candidates: frozenset[Subject]
    context: EvidenceContext


@dataclass(frozen=True)
class PartitionPosteriorEvidence:
    subjects: tuple[Subject, ...]
    entropy_bits: float
    sampled_partitions: int
    context: EvidenceContext

    def __post_init__(self) -> None:
        _require_finite(self.entropy_bits, "entropy_bits")
        if self.entropy_bits < 0:
            raise ValueError("entropy_bits must be non-negative")
        if self.sampled_partitions < 1:
            raise ValueError("sampled_partitions must be positive")


@dataclass(frozen=True)
class ProvenanceDistributionEvidence:
    subject: Subject
    probabilities: tuple[tuple[Subject, float], ...]
    context: EvidenceContext

    def __post_init__(self) -> None:
        if not self.probabilities:
            raise ValueError("provenance distribution must not be empty")
        total = 0.0
        origins: set[Subject] = set()
        for origin, probability in self.probabilities:
            _require_finite(probability, "probability")
            if not 0.0 <= probability <= 1.0:
                raise ValueError("probability must be within [0, 1]")
            if origin in origins:
                raise ValueError("provenance origins must be unique")
            origins.add(origin)
            total += probability
        if abs(total - 1.0) > 1e-9:
            raise ValueError("provenance probabilities must sum to 1")


@dataclass(frozen=True)
class IntersectionEvidence:
    observations: tuple[Subject, ...]
    candidates_before: int
    candidates_after: frozenset[Subject]
    context: EvidenceContext

    def __post_init__(self) -> None:
        if len(self.observations) < 2:
            raise ValueError("intersection requires at least two observations")
        if self.candidates_before < len(self.candidates_after):
            raise ValueError("intersection cannot increase its candidate set")


@dataclass(frozen=True)
class FlowConstraintEvidence:
    subject: Subject
    target: Subject
    amount: int
    unit: str
    context: EvidenceContext

    def __post_init__(self) -> None:
        _require_pair(self.subject, self.target)
        if self.amount < 0:
            raise ValueError("amount must be non-negative")
        if not self.unit:
            raise ValueError("unit must not be empty")


@dataclass(frozen=True)
class AbstentionEvidence:
    subjects: tuple[Subject, ...]
    reason: str
    context: EvidenceContext

    def __post_init__(self) -> None:
        if not self.subjects:
            raise ValueError("abstention requires at least one subject")
        if not self.reason:
            raise ValueError("abstention reason must not be empty")


@dataclass(frozen=True)
class CandidateEliminationEvidence:
    subject: Subject
    candidates_before: frozenset[Subject]
    eliminated: frozenset[Subject]
    context: EvidenceContext

    def __post_init__(self) -> None:
        if not self.candidates_before:
            raise ValueError("candidate elimination requires an initial set")
        if not self.eliminated:
            raise ValueError("candidate elimination requires removed candidates")
        if not self.eliminated <= self.candidates_before:
            raise ValueError("eliminated candidates must belong to the initial set")

    @property
    def candidates_after(self) -> frozenset[Subject]:
        return self.candidates_before - self.eliminated


@dataclass(frozen=True)
class GraphFractureEvidence:
    removed: frozenset[Subject]
    components_before: int
    components_after: int
    context: EvidenceContext

    def __post_init__(self) -> None:
        if not self.removed:
            raise ValueError("graph fracture requires removed subjects")
        if self.components_before < 1:
            raise ValueError("components_before must be positive")
        if self.components_after <= self.components_before:
            raise ValueError("graph fracture must increase the component count")


@dataclass(frozen=True)
class CorrespondentDistributionEvidence:
    """Finite-sample estimate of a target's persistent correspondent distribution.

    Scores are not constrained to ``[0, 1]`` because subtraction of an estimated
    background distribution can produce negative finite-sample values.
    """

    target: Subject
    scores: tuple[tuple[Subject, float], ...]
    observations: int
    batch_size: int
    context: EvidenceContext

    def __post_init__(self) -> None:
        if not self.scores:
            raise ValueError("correspondent scores must not be empty")
        correspondents: set[Subject] = set()
        total = 0.0
        for correspondent, score in self.scores:
            _require_pair(self.target, correspondent)
            _require_finite(score, "correspondent score")
            if correspondent in correspondents:
                raise ValueError("correspondents must be unique")
            correspondents.add(correspondent)
            total += score
        if abs(total - 1.0) > 1e-9:
            raise ValueError("correspondent scores must sum to one")
        if self.observations < 1:
            raise ValueError("observations must be positive")
        if self.batch_size < 2:
            raise ValueError("batch_size must be at least two")


@dataclass(frozen=True)
class PerfectMatchingEvidence:
    """Jointly optimal bijective message assignments for one observed round."""

    senders: tuple[Subject, ...]
    receivers: tuple[Subject, ...]
    optimal_assignments: tuple[tuple[tuple[Subject, Subject], ...], ...]
    log_likelihood: float
    context: EvidenceContext

    def __post_init__(self) -> None:
        if len(self.senders) < 2 or len(self.senders) != len(self.receivers):
            raise ValueError("perfect matching requires equal sides of size at least two")
        if len(set(self.senders)) != len(self.senders) or len(set(self.receivers)) != len(
            self.receivers
        ):
            raise ValueError("message nodes on each side must be unique")
        if not self.optimal_assignments:
            raise ValueError("perfect matching evidence requires an optimum")
        expected_senders = set(self.senders)
        expected_receivers = set(self.receivers)
        for assignment in self.optimal_assignments:
            if len(assignment) != len(self.senders):
                raise ValueError("every assignment must cover the round")
            if {sender for sender, _ in assignment} != expected_senders or {
                receiver for _, receiver in assignment
            } != expected_receivers:
                raise ValueError("every assignment must be a perfect matching")
        _require_finite(self.log_likelihood, "log_likelihood")


Evidence: TypeAlias = Union[
    OwnershipLikelihoodEvidence,
    CannotLinkEvidence,
    MappingEvidence,
    CandidateSetEvidence,
    PartitionPosteriorEvidence,
    ProvenanceDistributionEvidence,
    IntersectionEvidence,
    FlowConstraintEvidence,
    AbstentionEvidence,
    CandidateEliminationEvidence,
    GraphFractureEvidence,
    CorrespondentDistributionEvidence,
    PerfectMatchingEvidence,
]
