import pytest

from decluster.adaptations.pseudonym_graph import contract_evidence, contract_report
from decluster.domain import ContractedTransfer, PseudonymGraphConstructed
from decluster.experiments.pseudonym_graph_contract import fixture


def test_partial_clustering_preserves_unknown_singleton():
    sample, lookup = fixture()
    evidence = contract_evidence(sample, lookup)

    assert {vertex.identifier for vertex in evidence.vertices} == {
        "cluster-a",
        "cluster-x",
        "z",
    }


def test_direction_and_folded_parallel_transfer_attributes_are_preserved():
    sample, lookup = fixture()
    evidence = contract_evidence(sample, lookup)
    edges = {(edge.source.identifier, edge.target.identifier): edge for edge in evidence.edges}

    forward = edges[("cluster-a", "cluster-x")]
    assert (forward.transfers, forward.value) == (3, 600)
    assert (forward.first_height, forward.last_height) == (100, 140)
    assert ("cluster-x", "cluster-a") in edges
    assert ("cluster-a", "cluster-x") != ("cluster-x", "cluster-a")


def test_self_transfer_does_not_become_a_relational_edge():
    sample, lookup = fixture()
    evidence = contract_evidence(sample, lookup)

    assert {(vertex.identifier, count) for vertex, count in evidence.self_transfers} == {
        ("cluster-a", 1)
    }
    assert all(edge.source != edge.target for edge in evidence.edges)


def test_report_calls_the_vertices_pseudonyms_not_users():
    sample, lookup = fixture()
    report = contract_report(sample, lookup)

    assert isinstance(report.outcomes[0], PseudonymGraphConstructed)
    assert report.composition is None
    assert "pseudonyms" in report.limitations[2]


def test_typed_edge_rejects_an_invalid_height_span():
    sample, lookup = fixture()
    vertex = contract_evidence(sample, lookup).vertices

    with pytest.raises(ValueError, match="height span"):
        ContractedTransfer(vertex[0], vertex[1], 1, 10, 20, 19)
