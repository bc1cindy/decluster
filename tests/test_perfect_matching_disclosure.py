import pytest

from decluster.domain import Inconclusive, MessageAssignmentRecovered
from decluster.failure_modes.perfect_matching_disclosure import (
    PerfectMatchingScenario,
    analyze,
    evaluate,
    paired_examples,
)


def test_joint_assignment_is_unique_and_bijective():
    joint, _ = paired_examples()
    analysis = analyze(joint)
    outcome = evaluate(joint).outcomes[0]

    assert isinstance(outcome, MessageAssignmentRecovered)
    assert len(analysis.assignments) == 1
    assert analysis.assignments[0] == tuple(zip(joint.senders, joint.receivers))


def test_independent_maxima_do_not_form_the_joint_assignment():
    joint, _ = paired_examples()
    naive = tuple(max(range(3), key=row.__getitem__) for row in joint.profile_weights)

    assert naive == (0, 0, 2)
    assert len(set(naive)) < len(naive)


def test_uniform_profiles_preserve_all_perfect_matchings():
    _, control = paired_examples()
    analysis = analyze(control)
    report = evaluate(control)

    assert len(analysis.assignments) == 6
    assert isinstance(report.outcomes[0], Inconclusive)


def test_zero_probability_edges_are_excluded():
    joint, _ = paired_examples()
    scenario = PerfectMatchingScenario(
        "zero-edge",
        joint.senders,
        joint.receivers,
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    )

    assert analyze(scenario).assignments == (tuple(zip(scenario.senders, scenario.receivers)),)


def test_profile_matrix_must_match_the_round():
    joint, _ = paired_examples()

    with pytest.raises(ValueError, match="square"):
        PerfectMatchingScenario(
            joint.identifier,
            joint.senders,
            joint.receivers,
            joint.profile_weights[:-1],
        )


def test_report_does_not_claim_bitcoin_ownership():
    report = evaluate(paired_examples()[0])

    assert report.channels[0].identifier == "joint_round_assignment"
    assert report.composition is None
    assert "does not attribute Bitcoin ownership" in report.limitations[2]
