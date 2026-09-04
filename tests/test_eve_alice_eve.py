import pytest

from decluster.domain import CandidateNarrowing, Inconclusive, Subject, SubjectKind
from decluster.failure_modes.eve_alice_eve import (
    CounterpartyReturnScenario,
    ctp_consolidation_example,
    evaluate,
)


def test_two_returned_descendants_compound_the_counterparty_observation():
    scenario = ctp_consolidation_example()
    report = evaluate(scenario)
    intersection = report.channels[1].evidence[0]

    assert {candidate.identifier for candidate in intersection.candidates_after} == {
        "alice"
    }
    assert report.outcomes == (CandidateNarrowing(intersection),)
    assert report.composition is None


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
