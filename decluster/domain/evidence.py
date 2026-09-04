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
]
