"""Typed boundary for the legacy pseudonym-graph contraction."""

from ..domain import (
    AttackReport,
    ContractedTransfer,
    EvidenceChannel,
    EvidenceContext,
    PseudonymGraphEvidence,
    PseudonymGraphConstructed,
    Subject,
    SubjectKind,
)
from ..contraction import contract


def _cluster(identifier) -> Subject:
    return Subject(SubjectKind.CLUSTER, identifier)


def contract_evidence(sample, lookup) -> PseudonymGraphEvidence:
    """Contract a sample while preserving direction and folded transfer attributes."""
    graph = contract(sample, lookup=lookup, axes=False)
    vertices = tuple(
        _cluster(identifier) for identifier in sorted(graph.vertices, key=repr)
    )
    by_identifier = {vertex.identifier: vertex for vertex in vertices}
    edges = tuple(
        ContractedTransfer(
            by_identifier[source],
            by_identifier[target],
            attributes["transfers"],
            attributes["value"],
            attributes["first"],
            attributes["last"],
        )
        for (source, target), attributes in sorted(
            graph.edges.items(), key=lambda item: repr(item[0])
        )
    )
    self_transfers = tuple(
        (by_identifier[identifier], record["self_transfers"])
        for identifier, record in sorted(graph.vertices.items(), key=lambda item: repr(item[0]))
        if record["self_transfers"]
    )
    return PseudonymGraphEvidence(
        vertices,
        edges,
        self_transfers,
        EvidenceContext(
            adversary="observer with a partial clustering of Bitcoin addresses",
            observables=("directed transactions", "partial address-to-cluster lookup"),
            hypothesis="partial contraction yields an attributed pseudonym graph, not a complete user network",
            algorithm="decluster.contraction.contract with structure-only attributes",
            dataset="deterministic synthetic contraction fixture",
            limitations=(
                "the supplied lookup is a clustering hypothesis",
                "parallel transfers are folded rather than stored as separate edge objects",
            ),
        ),
    )


def contract_report(sample, lookup) -> AttackReport:
    evidence = contract_evidence(sample, lookup)
    return AttackReport(
        identifier="ctp.pseudonym-graph-representation",
        attack="partial-clustering graph contraction",
        subjects=evidence.vertices,
        channels=(EvidenceChannel("contracted_graph", (evidence,)),),
        outcomes=(PseudonymGraphConstructed(evidence),),
        limitations=(
            "deterministic synthetic fixture",
            "the partial clustering lookup is supplied",
            "vertices represent pseudonyms unless clustering completeness is independently established",
            "the report validates representation invariants, not deanonymization success",
        ),
    )
