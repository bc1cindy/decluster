"""Closed outcomes for adversarial analysis and partition operations."""

from dataclasses import dataclass
from math import isfinite
from typing import TypeAlias, Union

from .evidence import (
    CandidateEliminationEvidence,
    CoSpendEvidence,
    Evidence,
    GraphFractureEvidence,
    CorrespondentDistributionEvidence,
    PerfectMatchingEvidence,
    TransactionFingerprintEvidence,
    PseudonymGraphEvidence,
    UnanimousMappingLinksEvidence,
    IntersectionEvidence,
    ProvenanceDistributionEvidence,
    Subject,
    SubjectKind,
)


def _require_pair(subject: Subject, target: Subject) -> None:
    if subject == target:
        raise ValueError("subject and target must be distinct")


def _require_evidence(evidence: tuple[Evidence, ...]) -> None:
    if not evidence:
        raise ValueError("outcome requires evidence")


@dataclass(frozen=True)
class ClusterMerge:
    subject: Subject
    target: Subject
    evidence: tuple[Evidence, ...]

    def __post_init__(self) -> None:
        _require_pair(self.subject, self.target)
        _require_evidence(self.evidence)


@dataclass(frozen=True)
class MergeRefused:
    subject: Subject
    target: Subject
    evidence: tuple[Evidence, ...]
    reason: str

    def __post_init__(self) -> None:
        _require_pair(self.subject, self.target)
        _require_evidence(self.evidence)
        if not self.reason:
            raise ValueError("refusal reason must not be empty")


@dataclass(frozen=True)
class DeclusterSplit:
    original_cluster: Subject
    refined_clusters: tuple[frozenset[Subject], ...]
    evidence: tuple[Evidence, ...]

    def __post_init__(self) -> None:
        if self.original_cluster.kind is not SubjectKind.CLUSTER:
            raise ValueError("decluster split requires a cluster subject")
        if len(self.refined_clusters) < 2 or any(not part for part in self.refined_clusters):
            raise ValueError("decluster split requires at least two non-empty parts")
        flattened = [subject for part in self.refined_clusters for subject in part]
        if len(flattened) != len(set(flattened)):
            raise ValueError("decluster split parts must be disjoint")
        _require_evidence(self.evidence)


@dataclass(frozen=True)
class Attribution:
    subject: Subject
    attributed_to: Subject
    evidence: tuple[Evidence, ...]

    def __post_init__(self) -> None:
        _require_pair(self.subject, self.attributed_to)
        _require_evidence(self.evidence)


@dataclass(frozen=True)
class TransitiveMembership:
    subject: Subject
    target: Subject
    reason: str

    def __post_init__(self) -> None:
        _require_pair(self.subject, self.target)
        if not self.reason:
            raise ValueError("transitive membership reason must not be empty")


@dataclass(frozen=True)
class CandidateNarrowing:
    evidence: IntersectionEvidence


@dataclass(frozen=True)
class NoSharedCandidates:
    evidence: IntersectionEvidence

    def __post_init__(self) -> None:
        if self.evidence.candidates_after:
            raise ValueError("no-shared-candidates outcome requires an empty intersection")


@dataclass(frozen=True)
class CompleteProvenanceMeasured:
    evidence: ProvenanceDistributionEvidence


@dataclass(frozen=True)
class TruncatedProvenanceMeasured:
    evidence: ProvenanceDistributionEvidence


@dataclass(frozen=True)
class Inconclusive:
    subjects: tuple[Subject, ...]
    reason: str

    def __post_init__(self) -> None:
        if not self.subjects:
            raise ValueError("inconclusive outcome requires subjects")
        if not self.reason:
            raise ValueError("inconclusive reason must not be empty")


@dataclass(frozen=True)
class NodeCapped:
    observed: int
    limit: int

    def __post_init__(self) -> None:
        if self.limit < 1 or self.observed <= self.limit:
            raise ValueError("node cap requires observed > positive limit")


@dataclass(frozen=True)
class OracleRefused:
    reason: str

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError("oracle refusal reason must not be empty")


@dataclass(frozen=True)
class Unsupported:
    feature: str
    reason: str

    def __post_init__(self) -> None:
        if not self.feature or not self.reason:
            raise ValueError("unsupported outcome requires feature and reason")


@dataclass(frozen=True)
class NotObserved:
    observable: str

    def __post_init__(self) -> None:
        if not self.observable:
            raise ValueError("observable must not be empty")


@dataclass(frozen=True)
class AdditiveDecayMeasured:
    evidence: CandidateEliminationEvidence


@dataclass(frozen=True)
class GraphFractureMeasured:
    evidence: GraphFractureEvidence


@dataclass(frozen=True)
class PersistentCorrespondentRanked:
    evidence: CorrespondentDistributionEvidence
    correspondent: Subject
    margin: float

    def __post_init__(self) -> None:
        if self.correspondent not in dict(self.evidence.scores):
            raise ValueError("ranked correspondent must occur in evidence")
        if not isfinite(self.margin) or self.margin < 0:
            raise ValueError("ranking margin must be finite and non-negative")


@dataclass(frozen=True)
class MessageAssignmentRecovered:
    evidence: PerfectMatchingEvidence
    assignment: tuple[tuple[Subject, Subject], ...]

    def __post_init__(self) -> None:
        if len(self.evidence.optimal_assignments) != 1:
            raise ValueError("recovered assignment requires a unique optimum")
        if self.assignment != self.evidence.optimal_assignments[0]:
            raise ValueError("assignment must equal the unique optimum")


@dataclass(frozen=True)
class TransactionFingerprintObserved:
    evidence: TransactionFingerprintEvidence
    rule: str

    def __post_init__(self) -> None:
        if not self.rule:
            raise ValueError("fingerprint rule must not be empty")


@dataclass(frozen=True)
class PseudonymGraphConstructed:
    evidence: PseudonymGraphEvidence


@dataclass(frozen=True)
class ConditionalLinksMeasured:
    """Unanimous links measured within, and only within, a declared mapping model."""

    evidence: UnanimousMappingLinksEvidence


@dataclass(frozen=True)
class ReferenceOwnershipConflict:
    """A predicted merge conflicts with distinct ownership labels supplied by a fixture."""

    subject: Subject
    target: Subject
    evidence: CoSpendEvidence
    subject_owner: str
    target_owner: str

    def __post_init__(self) -> None:
        _require_pair(self.subject, self.target)
        if self.subject not in self.evidence.inputs or self.target not in self.evidence.inputs:
            raise ValueError("conflicting subjects must occur in the co-spend")
        if not self.subject_owner or not self.target_owner:
            raise ValueError("reference owner labels must not be empty")
        if self.subject_owner == self.target_owner:
            raise ValueError("ownership conflict requires distinct reference labels")


Outcome: TypeAlias = Union[
    ClusterMerge,
    MergeRefused,
    DeclusterSplit,
    Attribution,
    TransitiveMembership,
    CandidateNarrowing,
    NoSharedCandidates,
    CompleteProvenanceMeasured,
    TruncatedProvenanceMeasured,
    Inconclusive,
    NodeCapped,
    OracleRefused,
    Unsupported,
    NotObserved,
    AdditiveDecayMeasured,
    GraphFractureMeasured,
    PersistentCorrespondentRanked,
    MessageAssignmentRecovered,
    TransactionFingerprintObserved,
    PseudonymGraphConstructed,
    ConditionalLinksMeasured,
    ReferenceOwnershipConflict,
]
