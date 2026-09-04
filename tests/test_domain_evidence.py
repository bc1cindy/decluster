from dataclasses import FrozenInstanceError

import pytest

from decluster.domain import (
    Attribution,
    ClusterMerge,
    DeclusterSplit,
    Direction,
    EvidenceContext,
    NodeCapped,
    NotObserved,
    OwnershipLikelihoodEvidence,
    ProvenanceDistributionEvidence,
    MergeRefused,
    Subject,
    SubjectKind,
)


def context():
    return EvidenceContext(
        adversary="external observer",
        observables=("co-spend", "wallet fingerprint"),
        hypothesis="the coins share an owner",
        algorithm="fingerprint-v1",
        dataset="fixture-v1",
    )


def coin(identifier):
    return Subject(SubjectKind.COIN, identifier)


def test_ownership_evidence_is_immutable_and_directional():
    evidence = OwnershipLikelihoodEvidence(
        coin("a"), coin("b"), -2.5, context(), Direction.OPPOSES_COMMON_OWNERSHIP
    )

    with pytest.raises(FrozenInstanceError):
        evidence.log2_odds = 1.0
    with pytest.raises(ValueError, match="ownership direction"):
        OwnershipLikelihoodEvidence(
            coin("a"), coin("b"), 0.0, context(), Direction.DESCRIPTIVE
        )


def test_provenance_distribution_rejects_invalid_probabilities():
    with pytest.raises(ValueError, match="sum to 1"):
        ProvenanceDistributionEvidence(
            coin("target"), ((coin("a"), 0.7), (coin("b"), 0.2)), context()
        )


def test_outcomes_do_not_encode_refusal_as_a_boolean():
    evidence = OwnershipLikelihoodEvidence(
        coin("a"), coin("b"), -2.5, context(), Direction.OPPOSES_COMMON_OWNERSHIP
    )

    clustered = ClusterMerge(coin("a"), coin("b"), (evidence,))
    refused = MergeRefused(coin("a"), coin("b"), (evidence,), "net evidence opposes merge")
    attributed = Attribution(coin("a"), coin("b"), (evidence,))
    split = DeclusterSplit(
        Subject(SubjectKind.CLUSTER, "wallet"),
        (frozenset({coin("a")}), frozenset({coin("b")})),
        (evidence,),
    )

    assert type(clustered) is ClusterMerge
    assert type(refused) is MergeRefused
    assert type(attributed) is Attribution
    assert type(split) is DeclusterSplit


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: Subject(SubjectKind.COIN, ""), "identifier"),
        (lambda: Subject(SubjectKind.COIN, []), "hashable"),
        (lambda: NodeCapped(observed=10, limit=10), "observed"),
        (lambda: NotObserved(""), "observable"),
    ],
)
def test_invalid_domain_states_are_rejected(factory, message):
    with pytest.raises(ValueError, match=message):
        factory()
