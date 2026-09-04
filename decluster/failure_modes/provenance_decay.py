"""Additive candidate decay and structural fracture in provenance graphs."""

from dataclasses import dataclass

from ..domain import (
    AdditiveDecayMeasured,
    AttackReport,
    CandidateEliminationEvidence,
    EvidenceChannel,
    EvidenceContext,
    GraphFractureEvidence,
    GraphFractureMeasured,
    Inconclusive,
    Subject,
    SubjectKind,
)


@dataclass(frozen=True)
class ProvenanceDecayScenario:
    target: Subject
    candidates: frozenset[Subject]
    known_auxiliaries: frozenset[Subject]
    graph_nodes: frozenset[Subject]
    graph_edges: frozenset[frozenset[Subject]]

    def __post_init__(self) -> None:
        if self.target.kind is not SubjectKind.OUTPOINT:
            raise ValueError("target must be an outpoint")
        if not self.known_auxiliaries or not self.known_auxiliaries <= self.candidates:
            raise ValueError("known auxiliaries must be candidate origins")
        if not self.candidates <= self.graph_nodes:
            raise ValueError("candidate origins must be graph nodes")
        if any(
            len(edge) != 2 or not edge <= self.graph_nodes
            for edge in self.graph_edges
        ):
            raise ValueError("edges must connect two declared graph nodes")


def ctp_fracture_example() -> ProvenanceDecayScenario:
    bridge = Subject(SubjectKind.CLUSTER, "known-auxiliary")
    left = Subject(SubjectKind.CLUSTER, "left-origin")
    right = Subject(SubjectKind.CLUSTER, "right-origin")
    return ProvenanceDecayScenario(
        target=Subject(SubjectKind.OUTPOINT, ("target", 0)),
        candidates=frozenset({left, bridge, right}),
        known_auxiliaries=frozenset({bridge}),
        graph_nodes=frozenset({left, bridge, right}),
        graph_edges=frozenset({frozenset({left, bridge}), frozenset({bridge, right})}),
    )


def _component_count(nodes, edges):
    unseen = set(nodes)
    count = 0
    while unseen:
        count += 1
        frontier = [unseen.pop()]
        while frontier:
            current = frontier.pop()
            neighbors = {
                next(iter(edge - {current}))
                for edge in edges
                if current in edge
            }
            discovered = neighbors & unseen
            unseen -= discovered
            frontier.extend(discovered)
    return count


def evaluate(scenario: ProvenanceDecayScenario) -> AttackReport:
    context = EvidenceContext(
        adversary="observer with newly identified auxiliary entities",
        observables=("candidate origins", "provenance adjacency", "auxiliary labels"),
        hypothesis="identified auxiliaries can be excluded from the target's origins",
        algorithm="candidate elimination and component comparison",
        dataset="ctp synthetic provenance-fracture fixture",
        limitations=("graph and auxiliary labels are supplied by the fixture",),
    )
    elimination = CandidateEliminationEvidence(
        scenario.target, scenario.candidates, scenario.known_auxiliaries, context
    )
    remaining_nodes = scenario.graph_nodes - scenario.known_auxiliaries
    remaining_edges = frozenset(
        edge for edge in scenario.graph_edges if not edge & scenario.known_auxiliaries
    )
    before = _component_count(scenario.graph_nodes, scenario.graph_edges)
    after = _component_count(remaining_nodes, remaining_edges)
    channels = [EvidenceChannel("candidate_elimination", (elimination,))]
    outcomes = [AdditiveDecayMeasured(elimination)]
    if after > before:
        fracture = GraphFractureEvidence(
            scenario.known_auxiliaries, before, after, context
        )
        channels.append(EvidenceChannel("graph_fracture", (fracture,)))
        outcomes.append(GraphFractureMeasured(fracture))
    else:
        outcomes.append(
            Inconclusive(
                (scenario.target,), "auxiliary removal did not fracture the graph"
            )
        )
    return AttackReport(
        identifier="ctp.provenance-decay",
        attack="candidate elimination and provenance graph fracture",
        subjects=(scenario.target,) + tuple(
            sorted(scenario.graph_nodes, key=lambda subject: str(subject.identifier))
        ),
        channels=tuple(channels),
        outcomes=tuple(outcomes),
        limitations=(
            "synthetic fixture",
            "component growth does not by itself establish exponential deanonymization",
            "edge plausibility and private adversary information are not modeled",
        ),
    )
