"""Typed boundary for the legacy provenance-intersection evaluator."""

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Mapping, Optional, TypeAlias, Union

from ..domain import (
    AttackReport,
    CandidateNarrowing,
    EvidenceChannel,
    EvidenceContext,
    Inconclusive,
    IntersectionEvidence,
    NoSharedCandidates,
    Subject,
    SubjectKind,
)
from ..intersect import evaluate


class BlindCause(str, Enum):
    ORACLE_REFUSED = "oracle_refused"
    NODE_CAPPED = "node_capped"
    ZERO_LINK_MASS = "zero_link_mass"
    MIXED = "mixed"
    UNKNOWN = "unknown"
    NO_OBSERVED_ORIGIN = "no_observed_origin"


@dataclass(frozen=True)
class BranchTruncation:
    branch: Subject
    total: int
    oracle_refused: Optional[int]
    node_capped: Optional[int]
    zero_link_mass: Optional[int]
    unattributed: Optional[int]


@dataclass(frozen=True)
class CompleteIntersection:
    evidence: IntersectionEvidence


@dataclass(frozen=True)
class BlindIntersection:
    cause: BlindCause
    branches: tuple[Subject, ...]


IntersectionState: TypeAlias = Union[CompleteIntersection, BlindIntersection]


@dataclass(frozen=True)
class IntersectionReport:
    transaction: Subject
    branches: tuple[Subject, ...]
    sizes: tuple[int, ...]
    shared: tuple[tuple[Any, float, float], ...]
    collapsed: int
    collapsed_bits: Optional[float]
    truncation: Optional[tuple[BranchTruncation, ...]]
    state: IntersectionState
    _legacy: Mapping[str, Any]

    def as_legacy(self) -> dict[str, Any]:
        """Return a fresh copy of the evaluator's original result."""
        return deepcopy(dict(self._legacy))

    def as_attack_report(self, identifier: str) -> AttackReport:
        """Expose narrowing only when every branch was observable."""
        if isinstance(self.state, CompleteIntersection):
            channels = (EvidenceChannel("provenance_intersection", (self.state.evidence,)),)
            if self.state.evidence.candidates_after:
                outcomes = (CandidateNarrowing(self.state.evidence),)
            else:
                outcomes = (NoSharedCandidates(self.state.evidence),)
        else:
            channels = ()
            outcomes = (
                Inconclusive(
                    self.state.branches,
                    f"intersection is blind: {self.state.cause.value}",
                ),
            )
        return AttackReport(
            identifier=identifier,
            attack="provenance intersection",
            subjects=self.branches,
            channels=channels,
            outcomes=outcomes,
            limitations=("the narrowing is conditional on validation of the observed linkage",),
        )


def _outpoint(value: Any) -> Subject:
    return Subject(SubjectKind.OUTPOINT, value)


def _truncations(branches, totals, causes):
    if totals is None:
        return None
    records = []
    for branch, total, cause in zip(branches, totals, causes):
        records.append(
            BranchTruncation(
                branch=branch,
                total=total,
                oracle_refused=None if cause is None else cause["oracle_refused"],
                node_capped=None if cause is None else cause["node_capped"],
                zero_link_mass=None if cause is None else cause["zero_link_mass"],
                unattributed=None if cause is None else cause["unattributed"],
            )
        )
    return tuple(records)


def evaluate_report(
    candidate: Mapping[str, Any],
    signature_of: Callable[[Any], Mapping[Any, float]],
    **options: Any,
) -> IntersectionReport:
    """Evaluate an intersection and replace boolean blindness with a typed state."""
    legacy = evaluate(candidate, signature_of, **options)
    branches = tuple(_outpoint(value) for value in candidate.get("outpoints", ()))
    shared_subjects = frozenset(
        Subject(SubjectKind.CLUSTER, origin) for origin, _mass, _weight in legacy["shared"]
    )
    context = EvidenceContext(
        adversary="external on-chain observer",
        observables=("candidate provenance sets", "co-spend observation"),
        hypothesis="linked branches share candidate origin clusters",
        algorithm="provenance_intersection",
        limitations=("narrowing is conditional on independent validation of the co-spend",),
    )
    evidence = IntersectionEvidence(
        observations=branches,
        candidates_before=min(legacy["sizes"]) if legacy["sizes"] else 0,
        candidates_after=shared_subjects,
        context=context,
    )
    if legacy["blind"]:
        cause = legacy["blind_cause"] or BlindCause.NO_OBSERVED_ORIGIN.value
        state = BlindIntersection(BlindCause(cause), branches)
    else:
        state = CompleteIntersection(evidence)
    return IntersectionReport(
        transaction=Subject(SubjectKind.TRANSACTION, legacy["txid"]),
        branches=branches,
        sizes=tuple(legacy["sizes"]),
        shared=tuple(legacy["shared"]),
        collapsed=legacy["collapsed"],
        collapsed_bits=legacy["collapsed_bits"],
        truncation=_truncations(branches, legacy["truncated"], legacy["truncated_causes"]),
        state=state,
        _legacy=MappingProxyType(deepcopy(legacy)),
    )
