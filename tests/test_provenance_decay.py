from decluster.domain import AdditiveDecayMeasured, GraphFractureMeasured, Inconclusive
from decluster.failure_modes.provenance_decay import (
    ProvenanceDecayScenario,
    ctp_fracture_example,
    evaluate,
)


def test_known_auxiliary_causes_additive_candidate_decay():
    report = evaluate(ctp_fracture_example())
    evidence = report.channels[0].evidence[0]

    assert len(evidence.candidates_before) == 3
    assert len(evidence.candidates_after) == 2
    assert isinstance(report.outcomes[0], AdditiveDecayMeasured)


def test_bridge_removal_is_measured_as_a_separate_graph_fracture():
    report = evaluate(ctp_fracture_example())
    fracture = report.channels[1].evidence[0]

    assert (fracture.components_before, fracture.components_after) == (1, 2)
    assert isinstance(report.outcomes[1], GraphFractureMeasured)
    assert report.composition is None


def test_component_growth_does_not_claim_an_exponential_rate():
    report = evaluate(ctp_fracture_example())

    assert "does not by itself" in report.limitations[1]
    assert "edge plausibility" in report.limitations[2]


def test_non_bridge_removal_remains_structurally_inconclusive():
    scenario = ctp_fracture_example()
    left = next(
        node for node in scenario.graph_nodes if node.identifier == "left-origin"
    )
    report = evaluate(ProvenanceDecayScenario(
        scenario.target,
        scenario.candidates,
        frozenset({left}),
        scenario.graph_nodes,
        scenario.graph_edges,
    ))

    assert len(report.channels) == 1
    assert isinstance(report.outcomes[1], Inconclusive)
