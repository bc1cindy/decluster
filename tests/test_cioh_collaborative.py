import pytest

from decluster.cluster import cluster_cospends
from decluster.domain import ClusterMerge, CoSpendEvidence, ReferenceOwnershipConflict
from decluster.failure_modes.cioh_collaborative import evaluate


def test_explicit_cospends_apply_transitive_common_input_ownership():
    groups = cluster_cospends(("a", "b", "c", "d"), (("a", "b"), ("b", "c")))
    assert {frozenset(group) for group in groups} == {frozenset(("a", "b", "c")), frozenset(("d",))}


def test_collaborative_labels_expose_the_cioh_merge_conflict():
    report = evaluate("tx", {"alice-coin": "alice", "bob-coin": "bob"})
    assert isinstance(report.channels[0].evidence[0], CoSpendEvidence)
    assert [type(item) for item in report.outcomes] == [
        ClusterMerge,
        ReferenceOwnershipConflict,
    ]
    assert report.composition is None


def test_same_owner_control_has_the_merge_without_a_reference_conflict():
    report = evaluate("tx", {"coin-1": "alice", "coin-2": "alice"})
    assert [type(item) for item in report.outcomes] == [ClusterMerge]


def test_fixture_requires_two_labelled_coins():
    with pytest.raises(ValueError, match="at least two"):
        evaluate("tx", {"coin": "alice"})
