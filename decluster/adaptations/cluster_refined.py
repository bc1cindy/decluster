"""Typed adapter for the legacy ``cluster_refined`` return value.

The legacy engine exposes final groups, refused co-spend pairs, and additional
fingerprint links.  It does not expose an audit trail for every accepted
co-spend merge, so this adapter intentionally makes no claim about those
unreported decisions.
"""

from dataclasses import dataclass
from typing import Any, Iterable

from ..cluster import (
    ClusterPairDecision,
    PairDecisionStatus,
    cluster_refined_decisions,
)
from ..domain import (
    AttackReport,
    CannotLinkEvidence,
    ClusterMerge,
    Direction,
    EvidenceContext,
    EvidenceChannel,
    MergeRefused,
    NotObserved,
    Outcome,
    OwnershipLikelihoodEvidence,
    Subject,
    SubjectKind,
    TransitiveMembership,
)


LegacyRefusal = tuple[str, str, str, float, float, float]
LegacyLink = tuple[str, str, float]
LegacyResult = tuple[list[list[str]], list[LegacyRefusal], list[LegacyLink]]


def _transaction(txid: str) -> Subject:
    return Subject(SubjectKind.TRANSACTION, txid)


def _context(algorithm: str, observables: tuple[str, ...]) -> EvidenceContext:
    return EvidenceContext(
        adversary="external on-chain observer",
        observables=observables,
        hypothesis="the funding transactions represent coins controlled by one owner",
        algorithm=algorithm,
        limitations=(),
    )


@dataclass(frozen=True)
class ClusterRefinementReport:
    """Typed view of decisions that the legacy engine actually reports."""

    groups: tuple[tuple[str, ...], ...]
    merge_refusals: tuple[MergeRefused, ...]
    added_links: tuple[ClusterMerge, ...]
    pair_outcomes: tuple[Outcome, ...]
    pair_evidence: tuple[OwnershipLikelihoodEvidence, ...]
    legacy_refusals: tuple[LegacyRefusal, ...]
    legacy_links: tuple[LegacyLink, ...]

    def as_legacy(self) -> LegacyResult:
        """Return the original positional representation without semantic loss."""
        return (
            [list(group) for group in self.groups],
            list(self.legacy_refusals),
            list(self.legacy_links),
        )

    def as_attack_report(self, identifier: str) -> AttackReport:
        """Describe the legacy engine's observable decisions without composition."""
        reported = self.pair_outcomes + self.added_links
        outcomes = reported or (NotObserved("merge refusal or additional fingerprint link"),)
        by_algorithm = {}
        for outcome in reported:
            for item in getattr(outcome, "evidence", ()):
                by_algorithm.setdefault(item.context.algorithm, []).append(item)
        for item in self.pair_evidence:
            by_algorithm.setdefault(item.context.algorithm, []).append(item)
        subjects = tuple(
            _transaction(node)
            for node in dict.fromkeys(node for group in self.groups for node in group)
        )
        channels = tuple(
            EvidenceChannel(channel_id, tuple(items))
            for channel_id, items in sorted(by_algorithm.items())
        )
        return AttackReport(
            identifier=identifier,
            attack="fingerprint-aware cluster refinement",
            subjects=subjects,
            channels=channels,
            outcomes=outcomes,
            limitations=(
                "transitive membership is reported separately from directly evaluated merges",
            ),
        )


def _numeric_evidence(decision: ClusterPairDecision):
    subject, target = _transaction(decision.left), _transaction(decision.right)
    channels = (
        ("cluster_refined.cospend_prior", "co-spend", decision.cospend_prior_bits),
        ("cluster_refined.fingerprint", "wallet fingerprint", decision.fingerprint_bits),
        ("cluster_refined.amount", "transaction amounts", decision.amount_bits),
        ("cluster_refined.topology", "counterparty topology", decision.topology_bits),
        ("cluster_refined.provenance", "provenance overlap", decision.provenance_bits),
        ("cluster_refined.subset_sum", "input-output amounts", decision.subset_sum_bits),
    )
    return tuple(
        OwnershipLikelihoodEvidence(
            subject,
            target,
            bits,
            _context(algorithm, (observable,)),
            (
                Direction.SUPPORTS_COMMON_OWNERSHIP
                if bits > 0
                else Direction.OPPOSES_COMMON_OWNERSHIP
            ),
        )
        for algorithm, observable, bits in channels
        if bits
    )


def _pair_outcome(decision: ClusterPairDecision, evidence):
    subject, target = _transaction(decision.left), _transaction(decision.right)
    if decision.status is PairDecisionStatus.DIRECT_MERGE:
        return ClusterMerge(subject, target, evidence)
    if decision.status is PairDecisionStatus.TRANSITIVE_MEMBERSHIP:
        return TransitiveMembership(
            subject,
            target,
            "the pair shares a final component through other accepted relations",
        )
    cannot_link = CannotLinkEvidence(
        subject,
        target,
        _context("cluster_refined", ("co-spend",)),
        "fused evidence did not support the co-spend merge",
    )
    return MergeRefused(
        subject,
        target,
        (cannot_link,) + evidence,
        f"merge refused in spending transaction {decision.spending_txid}; "
        f"total evidence {decision.total_bits:g} bits",
    )


def _added_link(record: LegacyLink) -> ClusterMerge:
    left, right, score = record
    subject, target = _transaction(left), _transaction(right)
    evidence = OwnershipLikelihoodEvidence(
        subject,
        target,
        score,
        _context("cluster_refined.fingerprint_link", ("wallet fingerprint",)),
        Direction.SUPPORTS_COMMON_OWNERSHIP,
    )
    return ClusterMerge(subject, target, (evidence,))


def cluster_refined_report(
    nodes: Iterable[str],
    combiner: Any,
    **options: Any,
) -> ClusterRefinementReport:
    """Run ``cluster_refined`` and expose its reported decisions as domain types.

    ``options`` is passed through unchanged so existing callers can migrate
    without maintaining a second copy of the engine's evolving keyword API.
    """
    node_list = list(nodes)
    groups, refusals, links, decisions = cluster_refined_decisions(
        node_list, combiner, **options
    )
    legacy_refusals = tuple(tuple(record) for record in refusals)
    legacy_links = tuple(tuple(record) for record in links)
    decision_evidence = tuple(_numeric_evidence(decision) for decision in decisions)
    pair_outcomes = tuple(
        _pair_outcome(decision, evidence)
        for decision, evidence in zip(decisions, decision_evidence)
    )
    return ClusterRefinementReport(
        groups=tuple(tuple(group) for group in groups),
        merge_refusals=tuple(
            outcome for outcome in pair_outcomes if isinstance(outcome, MergeRefused)
        ),
        added_links=tuple(_added_link(record) for record in legacy_links),
        pair_outcomes=pair_outcomes,
        pair_evidence=tuple(item for evidence in decision_evidence for item in evidence),
        legacy_refusals=legacy_refusals,
        legacy_links=legacy_links,
    )
