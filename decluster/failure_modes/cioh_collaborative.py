"""Evaluate CIOH against an explicitly labelled collaborative co-spend."""

from __future__ import annotations

from itertools import combinations

from ..cluster import cluster_cospends
from ..domain import (
    AttackReport,
    ClusterMerge,
    CoSpendEvidence,
    EvidenceChannel,
    EvidenceContext,
    ReferenceOwnershipConflict,
    Subject,
    SubjectKind,
)


def evaluate(transaction_id: str, owner_by_coin: dict[str, str]) -> AttackReport:
    """Apply CIOH once and expose conflicts with supplied ownership labels.

    The labels are fixture inputs, not inferred identities or chain-wide truth.
    """
    if len(owner_by_coin) < 2:
        raise ValueError("a co-spend requires at least two labelled coins")
    if any(not coin or not owner for coin, owner in owner_by_coin.items()):
        raise ValueError("coin and owner labels must not be empty")
    coins = tuple(owner_by_coin)
    subjects = tuple(Subject(SubjectKind.COIN, coin) for coin in coins)
    transaction = Subject(SubjectKind.TRANSACTION, transaction_id)
    context = EvidenceContext(
        adversary="external observer applying common-input ownership",
        observables=("transaction inputs",),
        hypothesis="all inputs in one transaction share an owner",
        algorithm="common-input ownership union-find",
        limitations=("reference owner labels are supplied by the fixture",),
    )
    evidence = CoSpendEvidence(transaction=transaction, inputs=subjects, context=context)
    groups = cluster_cospends(coins, (coins,))
    cluster_by_coin = {
        coin: index for index, group in enumerate(groups) for coin in group
    }
    outcomes = []
    for left, right in combinations(subjects, 2):
        if cluster_by_coin[left.identifier] != cluster_by_coin[right.identifier]:
            continue
        outcomes.append(ClusterMerge(left, right, (evidence,)))
        left_owner = owner_by_coin[left.identifier]
        right_owner = owner_by_coin[right.identifier]
        if left_owner != right_owner:
            outcomes.append(
                ReferenceOwnershipConflict(
                    left, right, evidence, left_owner, right_owner
                )
            )
    return AttackReport(
        identifier=f"cioh-collaborative:{transaction_id}",
        attack="common-input ownership applied to a collaborative transaction",
        subjects=subjects,
        channels=(EvidenceChannel("co_spend", (evidence,)),),
        outcomes=tuple(outcomes),
        limitations=(
            "the deterministic fixture supplies participant ownership labels",
            "the result demonstrates one false merge, not its chain-wide prevalence",
            "a co-spend alone does not prove common ownership",
        ),
    )
