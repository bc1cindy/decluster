import pytest

from decluster.adaptations.intersection import (
    BlindCause,
    BlindIntersection,
    CompleteIntersection,
    evaluate_ancestry_reports,
    evaluate_report,
)
from decluster.adaptations.ancestry import ancestry_signature_report
from decluster.ancestry import TruncationSupport
from decluster.domain import SubjectKind


def candidate():
    return {"txid": "spend", "outpoints": [("a", 0), ("b", 1)]}


def test_surviving_origins_are_coins_unless_they_were_lifted_to_wallets():
    """The lift is what makes an origin a cluster, so the kind has to follow `cluster_of`."""
    signatures = {("a", 0): {"x": 1.0, "y": 1.0}, ("b", 1): {"x": 1.0, "z": 1.0}}

    unlifted = evaluate_report(candidate(), signatures.__getitem__)
    assert {s.kind for s in unlifted.state.evidence.candidates_after} == {SubjectKind.COIN}
    assert {s.identifier for s in unlifted.state.evidence.candidates_after} == {"x"}

    lifted = evaluate_report(
        candidate(), signatures.__getitem__, cluster_of={"x": "wallet", "y": "y", "z": "z"}
    )
    assert {s.kind for s in lifted.state.evidence.candidates_after} == {SubjectKind.CLUSTER}
    assert {s.identifier for s in lifted.state.evidence.candidates_after} == {"wallet"}


def test_complete_empty_intersection_is_not_blind():
    signatures = {("a", 0): {"x": 1.0}, ("b", 1): {"y": 1.0}}

    report = evaluate_report(candidate(), signatures.__getitem__)

    assert isinstance(report.state, CompleteIntersection)
    assert report.state.evidence.candidates_after == frozenset()
    assert report.as_legacy()["blind"] is False
    attack_report = report.as_attack_report("complete-empty")
    assert attack_report.channels[0].identifier == "provenance_intersection"
    assert attack_report.outcomes[0].evidence == report.state.evidence
    assert type(attack_report.outcomes[0]).__name__ == "NoSharedCandidates"


def test_oracle_refusal_is_a_typed_blind_state_with_branch_details():
    signatures = {("a", 0): {"x": 1.0}, ("b", 1): {"y": 1.0}}
    truncation = {
        ("a", 0): TruncationSupport(oracle_refused=1, node_capped=0),
        ("b", 1): TruncationSupport(oracle_refused=0, node_capped=0),
    }

    report = evaluate_report(
        candidate(), signatures.__getitem__, truncation_of=truncation.__getitem__
    )

    assert report.state == BlindIntersection(BlindCause.ORACLE_REFUSED, report.branches)
    assert report.truncation[0].oracle_refused == 1
    assert report.truncation[0].node_capped == 0
    assert report.as_legacy()["blind_cause"] == "oracle_refused"
    attack_report = report.as_attack_report("blind-oracle")
    assert attack_report.channels == ()
    assert attack_report.outcomes[0].reason == "intersection is blind: oracle_refused"


def test_empty_untruncated_branch_has_an_explicit_blind_cause():
    signatures = {("a", 0): {}, ("b", 1): {"y": 1.0}}
    zeros = {
        ("a", 0): TruncationSupport(oracle_refused=0, node_capped=0),
        ("b", 1): TruncationSupport(oracle_refused=0, node_capped=0),
    }

    report = evaluate_report(candidate(), signatures.__getitem__, truncation_of=zeros.__getitem__)

    assert isinstance(report.state, BlindIntersection)
    assert report.state.cause is BlindCause.NO_OBSERVED_ORIGIN


def test_legacy_copy_cannot_mutate_the_typed_report():
    signatures = {("a", 0): {"x": 1.0}, ("b", 1): {"x": 1.0}}
    report = evaluate_report(candidate(), signatures.__getitem__)

    legacy = report.as_legacy()
    legacy["sizes"].append(999)

    assert report.sizes == (1, 1)
    assert report.as_legacy()["sizes"] == [1, 1]


def test_atomic_ancestry_observations_drive_intersection():
    reports = {
        ("a", 0): ancestry_signature_report(("a", 0), fetch=coinbase),
        ("b", 1): ancestry_signature_report(("b", 1), fetch=coinbase),
    }

    report = evaluate_ancestry_reports(candidate(), reports.__getitem__)

    assert isinstance(report.state, CompleteIntersection)
    assert report.state.evidence.candidates_after == frozenset()


def coinbase(txid):
    return {"vin": [{"is_coinbase": True}], "vout": [{"value": 1}, {"value": 1}]}


def test_atomic_intersection_rejects_a_mismatched_report():
    wrong = ancestry_signature_report(("wrong", 0), fetch=coinbase)

    with pytest.raises(ValueError, match="does not match"):
        evaluate_ancestry_reports(candidate(), lambda outpoint: wrong)
