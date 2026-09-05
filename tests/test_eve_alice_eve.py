import pytest

from decluster.domain import CandidateNarrowing, Inconclusive, Subject, SubjectKind
from decluster.failure_modes.eve_alice_eve import (
    CounterpartyReturnScenario,
    accumulate,
    ctp_compounding_example,
    ctp_consolidation_example,
    evaluate,
)


def test_two_returned_descendants_narrow_to_the_one_shared_customer():
    scenario = ctp_consolidation_example()
    report = evaluate(scenario)
    intersection = report.channels[1].evidence[0]

    assert {candidate.identifier for candidate in intersection.candidates_after} == {
        "alice"
    }
    assert report.outcomes == (CandidateNarrowing(intersection),)


def test_the_accumulator_and_the_baseline_agree_on_what_survives():
    """Two independent intersections back the same claim; a disagreement is a defect in one."""
    scenario = ctp_compounding_example()
    survivors, _bits = accumulate(scenario)

    assert survivors == evaluate(scenario).channels[1].evidence[0].candidates_after


def test_the_loss_compounds_rather_than_adding_up():
    """The writeup's claim is about a rate, so the report carries the additive baseline too."""
    composition = evaluate(ctp_compounding_example()).composition

    assert composition.unit == "bits"
    assert composition.channel_ids == ("return_intersection",)
    # log2(8/1) accumulated over three intersections, against log2(8/5) for one strike per return.
    assert composition.value == pytest.approx(3.0)
    assert "0.68" in composition.interpretation
    assert "not a measured rate" in composition.interpretation


def test_no_composition_without_a_stated_candidate_universe():
    """The published two-return fixture states no universe, so it claims no accumulation."""
    assert evaluate(ctp_consolidation_example()).composition is None


def test_one_return_remains_inconclusive_without_behavioral_prior():
    scenario = ctp_consolidation_example()
    report = evaluate(
        CounterpartyReturnScenario(
            scenario.counterparty,
            scenario.deposited_inputs[:1],
            scenario.candidate_customers[:1],
        )
    )

    assert isinstance(report.outcomes[0], Inconclusive)
    assert len(report.channels) == 1


def test_report_does_not_turn_privileged_knowledge_into_attribution():
    report = evaluate(ctp_consolidation_example())

    assert (
        "private transaction records"
        in report.channels[0].evidence[0].context.adversary
    )
    assert "not identity attribution" in report.limitations[2]
    assert "collaborative deposit" in report.limitations[3]


def test_scenario_requires_ambiguous_candidate_sets():
    scenario = ctp_consolidation_example()
    with pytest.raises(ValueError, match="ambiguous"):
        CounterpartyReturnScenario(
            scenario.counterparty,
            scenario.deposited_inputs,
            (
                scenario.candidate_customers[0],
                frozenset({Subject(SubjectKind.CLUSTER, "alice")}),
            ),
        )
