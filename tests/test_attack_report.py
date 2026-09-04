import pytest

from decluster.domain import (
    AttackReport,
    ClusterMerge,
    Direction,
    EvidenceChannel,
    EvidenceContext,
    ExperimentalComposition,
    OwnershipLikelihoodEvidence,
    Subject,
    SubjectKind,
)


def fixture():
    left = Subject(SubjectKind.COIN, "left")
    right = Subject(SubjectKind.COIN, "right")
    context = EvidenceContext(
        adversary="external observer",
        observables=("fingerprint",),
        hypothesis="common ownership",
        algorithm="fingerprint-v1",
    )
    evidence = OwnershipLikelihoodEvidence(
        left, right, 3.0, context, Direction.SUPPORTS_COMMON_OWNERSHIP
    )
    outcome = ClusterMerge(left, right, (evidence,))
    channel = EvidenceChannel("fingerprint", (evidence,))
    return left, right, outcome, channel


def test_report_preserves_channels_when_composition_is_present():
    left, right, outcome, channel = fixture()
    composition = ExperimentalComposition(
        method="sum for comparison only",
        channel_ids=("fingerprint",),
        value=3.0,
        unit="bits",
        interpretation="positive values favor the tested ownership hypothesis",
    )

    report = AttackReport(
        "fixture-report",
        "fingerprint matching",
        (left, right),
        (channel,),
        (outcome,),
        ("synthetic fixture",),
        composition,
    )

    assert report.channels == (channel,)
    assert report.evidence() == channel.evidence


def test_composition_cannot_reference_an_absent_channel():
    left, right, outcome, channel = fixture()
    composition = ExperimentalComposition(
        "sum", ("amount",), 1.0, "bits", "diagnostic only"
    )

    with pytest.raises(ValueError, match="unknown channels"):
        AttackReport(
            "fixture-report",
            "fingerprint matching",
            (left, right),
            (channel,),
            (outcome,),
            (),
            composition,
        )


def test_report_rejects_duplicate_channels_and_subjects():
    left, right, outcome, channel = fixture()

    with pytest.raises(ValueError, match="unique subjects"):
        AttackReport("id", "attack", (left, left), (channel,), (outcome,), ())
    with pytest.raises(ValueError, match="channel identifiers"):
        AttackReport("id", "attack", (left, right), (channel, channel), (outcome,), ())
