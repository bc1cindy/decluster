from decluster.adaptations.intersection import (
    BlindCause,
    BlindIntersection,
    CompleteIntersection,
    evaluate_report,
)
from decluster.ancestry import TruncationSupport


def candidate():
    return {"txid": "spend", "outpoints": [("a", 0), ("b", 1)]}


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
