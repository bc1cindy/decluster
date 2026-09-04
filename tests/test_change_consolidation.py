import pytest

from decluster.domain import CandidateNarrowing, NoSharedCandidates, Subject, SubjectKind
from decluster.failure_modes.change_consolidation import (
    ChangeConsolidationScenario,
    ctp_example,
    evaluate,
)


def test_change_consolidation_links_the_prior_payments_conditionally():
    scenario = ctp_example()
    report = evaluate(scenario)
    intersection = report.channels[1].evidence[0]
    assert intersection.observations == scenario.payments
    assert {candidate.identifier for candidate in intersection.candidates_after} == {
        "alice"
    }
    assert report.outcomes == (CandidateNarrowing(intersection),)
    assert report.composition is None


def test_change_consolidation_preserves_both_required_assumptions():
    report = evaluate(ctp_example())
    assert (
        "change identification"
        in report.channels[0].evidence[0].context.limitations[0]
    )
    assert (
        "both change identifications"
        in report.channels[1].evidence[0].context.limitations[0]
    )
    assert "collaborative co-spend" in report.limitations[2]


def test_disjoint_change_candidates_do_not_create_an_owner():
    scenario = ctp_example()
    report = evaluate(ChangeConsolidationScenario(
        scenario.payments,
        scenario.change_outputs,
        (
            scenario.candidate_owners[0],
            frozenset(
                {
                    Subject(SubjectKind.CLUSTER, "carol"),
                    Subject(SubjectKind.CLUSTER, "dave"),
                }
            ),
        ),
    ))
    assert isinstance(report.outcomes[0], NoSharedCandidates)


@pytest.mark.parametrize("field", ["payments", "change_outputs"])
def test_scenario_rejects_duplicate_observations(field):
    scenario = ctp_example()
    values = getattr(scenario, field)
    arguments = {
        "payments": scenario.payments,
        "change_outputs": scenario.change_outputs,
        "candidate_owners": scenario.candidate_owners,
    }
    arguments[field] = (values[0], values[0])
    with pytest.raises(ValueError, match="distinct"):
        ChangeConsolidationScenario(**arguments)
