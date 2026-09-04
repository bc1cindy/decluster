"""Typed results for provenance signatures and bounded ancestry walks."""

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, TypeAlias, Union

from ..ancestry import TruncationSupport, ancestry_signature_and_truncation
from ..domain import (
    AttackReport,
    CompleteProvenanceMeasured,
    EvidenceChannel,
    EvidenceContext,
    Inconclusive,
    NotObserved,
    ProvenanceDistributionEvidence,
    Subject,
    SubjectKind,
    TruncatedProvenanceMeasured,
)


@dataclass(frozen=True)
class TruncationBreakdown:
    oracle_refused: int
    node_capped: int
    zero_link_mass: int
    unattributed: int

    def __post_init__(self) -> None:
        if min(
            self.oracle_refused,
            self.node_capped,
            self.zero_link_mass,
            self.unattributed,
        ) < 0:
            raise ValueError("truncation counts must be non-negative")

    @property
    def total(self) -> int:
        return (
            self.oracle_refused
            + self.node_capped
            + self.zero_link_mass
            + self.unattributed
        )


@dataclass(frozen=True)
class CompleteAncestry:
    evidence: ProvenanceDistributionEvidence


@dataclass(frozen=True)
class TruncatedAncestry:
    evidence: Optional[ProvenanceDistributionEvidence]
    truncation: TruncationBreakdown

    def __post_init__(self) -> None:
        if self.truncation.total == 0:
            raise ValueError("truncated ancestry requires a truncation cause")


@dataclass(frozen=True)
class UnobservedAncestry:
    reason: str

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError("unobserved ancestry reason must not be empty")


AncestryState: TypeAlias = Union[CompleteAncestry, TruncatedAncestry, UnobservedAncestry]


@dataclass(frozen=True)
class AncestryReport:
    target: Subject
    distribution: tuple[tuple[Subject, float], ...]
    truncation: TruncationBreakdown
    state: AncestryState

    def as_legacy(self) -> tuple[dict[Any, float], TruncationSupport]:
        distribution = {subject.identifier: mass for subject, mass in self.distribution}
        support = TruncationSupport(
            oracle_refused=self.truncation.oracle_refused,
            node_capped=self.truncation.node_capped,
            unattributed=self.truncation.unattributed,
            zero_link_mass=self.truncation.zero_link_mass,
        )
        return distribution, support

    def as_attack_report(self, identifier: str) -> AttackReport:
        """Expose provenance measurement without interpreting it as privacy."""
        evidence = getattr(self.state, "evidence", None)
        channels = (
            (EvidenceChannel("absorbing_ancestry_walk", (evidence,)),)
            if evidence is not None
            else ()
        )
        if isinstance(self.state, CompleteAncestry):
            outcomes = (CompleteProvenanceMeasured(self.state.evidence),)
        elif isinstance(self.state, TruncatedAncestry):
            if self.state.evidence is None:
                outcomes = (
                    Inconclusive((self.target,), "ancestry boundary is entirely truncated"),
                )
            else:
                outcomes = (TruncatedProvenanceMeasured(self.state.evidence),)
        else:
            outcomes = (NotObserved("positive-mass ancestry boundary"),)
        return AttackReport(
            identifier=identifier,
            attack="provenance measurement",
            subjects=(self.target,),
            channels=channels,
            outcomes=outcomes,
            limitations=("this report measures model-relative provenance, not privacy",),
        )


def ancestry_signature_report(
    target: Any,
    depth: int = 6,
    fetch: Optional[Callable[[Any], Mapping[str, Any]]] = None,
    link_oracle: Optional[Callable[[list[int], list[int]], Any]] = None,
    max_nodes: Optional[int] = None,
) -> AncestryReport:
    """Run one ancestry walk and distinguish complete, truncated, and unseen states."""
    options = {"depth": depth, "fetch": fetch, "max_nodes": max_nodes}
    if link_oracle is not None:
        options["link_oracle"] = link_oracle
    distribution, support = ancestry_signature_and_truncation(target, **options)
    target_subject = Subject(SubjectKind.COIN, target)
    typed_distribution = tuple(
        (Subject(SubjectKind.COIN, origin), mass)
        for origin, mass in distribution.items()
    )
    truncation = TruncationBreakdown(
        oracle_refused=support.oracle_refused,
        node_capped=support.node_capped,
        zero_link_mass=support.zero_link_mass,
        unattributed=support.unattributed,
    )
    evidence = None
    if typed_distribution:
        limitations = ["the distribution is conditional on the selected link model"]
        if truncation.total:
            limitations.append(
                "legacy output counts truncated boundary atoms but does not identify "
                "them individually"
            )
        evidence = ProvenanceDistributionEvidence(
            subject=target_subject,
            probabilities=typed_distribution,
            context=EvidenceContext(
                adversary="external on-chain observer",
                observables=("transaction graph", "input-output link model"),
                hypothesis="the target descends from the reported boundary coins",
                algorithm="absorbing_ancestry_walk",
                limitations=tuple(limitations),
            ),
        )
    if truncation.total:
        state = TruncatedAncestry(evidence, truncation)
    elif evidence is None:
        state = UnobservedAncestry("the walk produced no positive-mass boundary")
    else:
        state = CompleteAncestry(evidence)
    return AncestryReport(target_subject, typed_distribution, truncation, state)
