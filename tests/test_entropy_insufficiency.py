import pytest

from decluster.domain import CandidateNarrowing
from decluster.failure_modes.entropy_insufficiency import EntropyScenario, evaluate, paired_examples


def test_equal_point_entropy_has_different_longitudinal_survivors():
    brittle, overlapping = paired_examples()
    brittle_report = evaluate(brittle)
    overlapping_report = evaluate(overlapping)

    assert brittle.entropy_bits == pytest.approx(2.0)
    assert overlapping.entropy_bits == pytest.approx(2.0)
    assert len(brittle_report.outcomes[0].evidence.candidates_after) == 1
    assert len(overlapping_report.outcomes[0].evidence.candidates_after) == 2
    assert all(isinstance(report.outcomes[0], CandidateNarrowing) for report in (
        brittle_report, overlapping_report,
    ))


def test_counterexample_preserves_posterior_and_intersection_as_separate_channels():
    report = evaluate(paired_examples()[0])

    assert tuple(channel.identifier for channel in report.channels) == (
        "initial_posterior",
        "longitudinal_intersection",
    )
    assert report.composition is None
    assert "does not imply" in report.limitations[1]
    assert "not a privacy score" in report.limitations[3]


def test_observations_must_be_subsets_of_the_declared_posterior():
    scenario, _ = paired_examples()
    unknown = scenario.target

    with pytest.raises(ValueError, match="subsets of the posterior"):
        EntropyScenario(
            scenario.identifier,
            scenario.target,
            scenario.probabilities,
            ((scenario.observations[0][0], frozenset({unknown})), scenario.observations[1]),
        )


def test_posterior_must_be_normalized():
    scenario, _ = paired_examples()

    with pytest.raises(ValueError, match="sum to one"):
        EntropyScenario(
            scenario.identifier,
            scenario.target,
            tuple((candidate, 0.2) for candidate, _ in scenario.probabilities),
            scenario.observations,
        )
