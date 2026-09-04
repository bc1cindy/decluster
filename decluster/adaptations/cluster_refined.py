"""Typed adapter for the legacy ``cluster_refined`` return value.

The legacy engine exposes final groups, refused co-spend pairs, and additional
fingerprint links.  It does not expose an audit trail for every accepted
co-spend merge, so this adapter intentionally makes no claim about those
unreported decisions.
"""

from dataclasses import dataclass
from typing import Any, Iterable

from ..cluster import cluster_refined
from ..domain import (
    CannotLinkEvidence,
    ClusterMerge,
    Direction,
    EvidenceContext,
    MergeRefused,
    OwnershipLikelihoodEvidence,
    Subject,
    SubjectKind,
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
        limitations=("legacy engine does not report every accepted co-spend merge",),
    )


@dataclass(frozen=True)
class ClusterRefinementReport:
    """Typed view of decisions that the legacy engine actually reports."""

    groups: tuple[tuple[str, ...], ...]
    merge_refusals: tuple[MergeRefused, ...]
    added_links: tuple[ClusterMerge, ...]
    legacy_refusals: tuple[LegacyRefusal, ...]
    legacy_links: tuple[LegacyLink, ...]

    def as_legacy(self) -> LegacyResult:
        """Return the original positional representation without semantic loss."""
        return (
            [list(group) for group in self.groups],
            list(self.legacy_refusals),
            list(self.legacy_links),
        )


def _refusal(record: LegacyRefusal) -> MergeRefused:
    left, right, spending_txid, fingerprint_bits, amount_bits, fused_bits = record
    subject, target = _transaction(left), _transaction(right)
    evidence = [
        CannotLinkEvidence(
            subject,
            target,
            _context("cluster_refined", ("co-spend", "wallet fingerprint")),
            "reported co-spend merge refusal",
        )
    ]
    if fingerprint_bits:
        evidence.append(
            OwnershipLikelihoodEvidence(
                subject,
                target,
                fingerprint_bits,
                _context("cluster_refined.fingerprint", ("wallet fingerprint",)),
                (
                    Direction.SUPPORTS_COMMON_OWNERSHIP
                    if fingerprint_bits > 0
                    else Direction.OPPOSES_COMMON_OWNERSHIP
                ),
            )
        )
    if amount_bits:
        evidence.append(
            OwnershipLikelihoodEvidence(
                subject,
                target,
                amount_bits,
                _context("cluster_refined.amount", ("transaction amounts",)),
                (
                    Direction.SUPPORTS_COMMON_OWNERSHIP
                    if amount_bits > 0
                    else Direction.OPPOSES_COMMON_OWNERSHIP
                ),
            )
        )
    return MergeRefused(
        subject,
        target,
        tuple(evidence),
        f"merge refused in spending transaction {spending_txid}; reported fused evidence {fused_bits:g} bits",
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
    groups, refusals, links = cluster_refined(node_list, combiner, **options)
    legacy_refusals = tuple(tuple(record) for record in refusals)
    legacy_links = tuple(tuple(record) for record in links)
    return ClusterRefinementReport(
        groups=tuple(tuple(group) for group in groups),
        merge_refusals=tuple(_refusal(record) for record in legacy_refusals),
        added_links=tuple(_added_link(record) for record in legacy_links),
        legacy_refusals=legacy_refusals,
        legacy_links=legacy_links,
    )
