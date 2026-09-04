import pytest

from decluster.domain import (
    CandidateNarrowing,
    CandidateSetEvidence,
    IntersectionEvidence,
    NoSharedCandidates,
    Subject,
    SubjectKind,
)
from decluster.failure_modes.equal_output_consolidation import (
    ConsolidationScenario,
    ctp_example,
    evaluate,
)


def test_consolidation_retroactively_narrows_two_ambiguous_outputs():
    scenario = ctp_example()
    report = evaluate(scenario)

    assert tuple(len(candidates) for candidates in scenario.candidate_sets) == (3, 3)
    assert tuple(channel.identifier for channel in report.channels) == (
        "candidate_origins",
        "consolidation_intersection",
    )
    assert all(
        isinstance(item, CandidateSetEvidence) for item in report.channels[0].evidence
    )
    intersection = report.channels[1].evidence[0]
    assert isinstance(intersection, IntersectionEvidence)
    assert {candidate.identifier for candidate in intersection.candidates_after} == {"alice"}
    assert report.outcomes == (CandidateNarrowing(intersection),)
    assert report.composition is None


def test_scenario_rejects_an_output_that_was_not_ambiguous():
    scenario = ctp_example()

    with pytest.raises(ValueError, match="ambiguous"):
        ConsolidationScenario(
            scenario.outputs,
            (scenario.candidate_sets[0], frozenset({next(iter(scenario.candidate_sets[1]))})),
        )


def test_result_declares_that_the_consolidation_link_is_conditional():
    report = evaluate(ctp_example())
    intersection = report.channels[1].evidence[0]

    assert "conditional" in intersection.context.limitations[0]
    assert "collaborative consolidation" in report.limitations[2]


def test_disjoint_candidate_sets_refuse_instead_of_claiming_narrowing():
    scenario = ctp_example()
    disjoint = ConsolidationScenario(
        scenario.outputs,
        (
            scenario.candidate_sets[0],
            frozenset({
                Subject(SubjectKind.CLUSTER, "dave"),
                Subject(SubjectKind.CLUSTER, "erin"),
            }),
        ),
    )

    report = evaluate(disjoint)

    assert report.channels[1].evidence[0].candidates_after == frozenset()
    assert isinstance(report.outcomes[0], NoSharedCandidates)
