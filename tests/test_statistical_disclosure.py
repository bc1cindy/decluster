import pytest

from decluster.domain import Inconclusive, PersistentCorrespondentRanked
from decluster.failure_modes.statistical_disclosure import (
    StatisticalDisclosureScenario,
    estimate,
    evaluate,
    paired_examples,
)


def test_repeated_rounds_recover_the_persistent_correspondent():
    persistent, _ = paired_examples()
    report = evaluate(persistent)
    outcome = report.outcomes[0]

    assert isinstance(outcome, PersistentCorrespondentRanked)
    assert outcome.correspondent.identifier == "alice"
    assert outcome.margin == pytest.approx(1.0)
    assert dict(outcome.evidence.scores) == pytest.approx(
        dict(zip(persistent.correspondents, (1.0, 0.0, 0.0, 0.0)))
    )


def test_background_matched_control_does_not_invent_a_correspondent():
    _, control = paired_examples()
    report = evaluate(control)

    assert isinstance(report.outcomes[0], Inconclusive)
    assert dict(estimate(control).scores) == pytest.approx(
        dict(zip(control.correspondents, control.background_distribution))
    )


def test_report_keeps_model_scope_and_has_no_composition():
    report = evaluate(paired_examples()[0])

    assert report.channels[0].identifier == "correspondent_distribution"
    assert report.composition is None
    assert "does not attribute Bitcoin ownership" in report.limitations[2]


def test_rounds_must_have_a_consistent_batch_size():
    scenario, _ = paired_examples()

    with pytest.raises(ValueError, match="one batch size"):
        StatisticalDisclosureScenario(
            scenario.identifier,
            scenario.target,
            scenario.correspondents,
            scenario.background_distribution,
            scenario.rounds + ((scenario.correspondents[0],),),
        )


def test_background_distribution_must_be_normalized():
    scenario, _ = paired_examples()

    with pytest.raises(ValueError, match="sum to one"):
        StatisticalDisclosureScenario(
            scenario.identifier,
            scenario.target,
            scenario.correspondents,
            (0.2, 0.2, 0.2, 0.2),
            scenario.rounds,
        )
