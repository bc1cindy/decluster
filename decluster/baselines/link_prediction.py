"""Link prediction driven by de-anonymization, next to the same predictor without it.

The mechanism, stated so it can be checked: run the faithful 2009 propagation
(:mod:`decluster.baselines.narayanan_shmatikov`) between a target view and an auxiliary view,
pull the auxiliary view's adjacency back onto target vertices through the mapping it returns,
and score candidate pairs on the enlarged neighbourhoods.  The structure-only arm applies the
*same* score to the target view alone.  The two arms therefore differ in one thing only —
whether the de-anonymized auxiliary view is available — which is what makes the comparison a
statement about de-anonymization rather than about two different predictors.

**This is not a reproduction of the 2011 Narayanan--Shmatikov link-prediction result.** That
paper is not in this checkout.  What is implemented here is the mechanism its title describes,
a mapping obtained by de-anonymization used as the feature that predicts links; its feature
set, its parameters, its dataset and its numbers are unknown to this module and no number or
parameter here may be attributed to Narayanan and Shmatikov.  The paper-case reproduction
stays an open cell of the fidelity matrix.

Scope, narrowly: no vertex attributes, no timestamps, no edge values, no supervised model, no
seed discovery.  The mapping is direction-aware because propagation is; the prediction is
undirected, because a common-neighbour score is.  Seeds are supplied by the caller together
with the provenance string that says where they came from, since a mapping propagated from
seeds drawn out of a withheld correspondence measures something different from one propagated
from independently observed labels, and the difference is not visible in the scores.

The graph interface is the structural subset :class:`views.PseudonymGraph` exposes —
``vertices``, ``_in`` and ``_out`` — the same subset the propagation consumes.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Hashable, Iterable, Mapping, Sequence

from ..graph_deanon import exact_auc, structural_score
from ..reproducibility import separable
from .ns_social_attack import propagate

Vertex = Hashable
Pair = tuple[Vertex, Vertex]


def neighbourhoods(graph) -> dict[Vertex, set[Vertex]]:
    """Undirected adjacency of a directed view, one set per vertex."""

    return {v: set(graph._out.get(v, ())) | set(graph._in.get(v, ()))
            for v in graph.vertices}


def transferred_neighbourhoods(target, auxiliary, mapping: Mapping[Vertex, Vertex]):
    """Target adjacency enlarged by every auxiliary edge the mapping can pull back.

    An auxiliary edge is transferable only when *both* of its endpoints are images of target
    vertices; an auxiliary vertex the mapping never claimed has no target identity, so its
    edges say nothing about the target view.  Returns `(neighbourhoods, new_pairs)` where
    `new_pairs` counts the undirected pairs the transfer added that the target did not
    already hold — the size of the evidence the arm is being given, which is zero when
    propagation mapped too little for any auxiliary edge to land inside the mapped set.
    """

    neighbours = neighbourhoods(target)
    preimage = {image: node for node, image in mapping.items()}
    new_pairs = 0
    for image, node in preimage.items():
        for other_image in auxiliary._out.get(image, ()):
            other = preimage.get(other_image)
            if other is None or other == node:
                continue
            if other not in neighbours.setdefault(node, set()):
                new_pairs += 1
            neighbours[node].add(other)
            neighbours.setdefault(other, set()).add(node)
    return neighbours, new_pairs


def score(neighbours: Mapping[Vertex, set], u: Vertex, v: Vertex) -> int:
    """Common neighbours over closed neighbourhoods.

    On a pair the graph does not join this is exactly the classic common-neighbour count
    (`graph_deanon.structural_score`).  On a pair it does join it is that count plus two,
    because each endpoint then appears in the other's closed neighbourhood.  That term is
    what carries a *directly* transferred edge: without it the arm would throw away the
    auxiliary view's plainest statement, "these two transacted".  In the structure-only arm
    it is identically zero, since the pairs being scored are by construction the ones the
    residual target view does not join.
    """

    left = neighbours.get(u, frozenset()) | {u}
    right = neighbours.get(v, frozenset()) | {v}
    return len(left & right)


def open_score(neighbours: Mapping[Vertex, set], u: Vertex, v: Vertex) -> int:
    """`score` with the closed term ablated: literally `graph_deanon.structural_score`.

    The whole result rests on the closed term, so the ablation is a parameter rather than an
    argument: pass it as `scorer` and the de-anonymization arm keeps the transferred adjacency
    but is no longer allowed to read a transferred edge as evidence for the pair it joins.
    `RESULTS-link-prediction.md` publishes what happens then, which is that the arm's advantage
    does not shrink, it disappears.
    """

    return structural_score(u, v, neighbours)


def candidate_pairs(graph) -> list[Pair]:
    """Every unordered pair of vertices the view does not already join.

    Quadratic in the vertex count and deliberately uncapped: it is for controlled runs, and a
    caller working on a real view should pass the candidate set its own observation policy
    selects rather than materialise this.
    """

    neighbours = neighbourhoods(graph)
    return [(u, v) for u, v in combinations(sorted(graph.vertices, key=repr), 2)
            if v not in neighbours.get(u, ())]


@dataclass(frozen=True)
class Prediction:
    """A run of the attack: the mapping it propagated and what it predicts from it."""

    mapping: dict[Vertex, Vertex]
    rounds: int
    transferred_pairs: int
    candidates: tuple[Pair, ...]
    scores: tuple[int, ...]

    def ranked(self) -> list[tuple[Pair, int]]:
        """Candidates highest score first; ties keep the order they were supplied in."""

        return sorted(zip(self.candidates, self.scores), key=lambda item: -item[1])

    def declared(self, cutoff: int) -> list[Pair]:
        return [pair for pair, value in zip(self.candidates, self.scores) if value >= cutoff]


def predict(target, auxiliary, seeds: Mapping[Vertex, Vertex], candidates: Iterable[Pair], *,
            seed_provenance: str, theta: float = 1.5, scorer=score) -> Prediction:
    """Propagate, transfer the auxiliary view's edges, score the candidates.

    `seed_provenance` is required and unused by the computation: it is here so a caller cannot
    obtain a prediction without stating where its seeds came from, which is the fact that
    decides whether the run is an attack or a demonstration of what an attack would do with an
    identity it was handed.
    """

    result = propagate(target, auxiliary, seeds, theta=theta)
    neighbours, new_pairs = transferred_neighbourhoods(target, auxiliary, result.mapping)
    candidates = tuple(candidates)
    return Prediction(mapping=dict(result.mapping), rounds=result.rounds,
                      transferred_pairs=new_pairs, candidates=candidates,
                      scores=tuple(scorer(neighbours, u, v) for u, v in candidates))


@dataclass(frozen=True)
class Arm:
    """One predictor's showing on the scored pairs, at one cutoff."""

    name: str
    declared: int
    correct: int
    precision: float | None
    recall: float
    auc: float | None


def _arm(name: str, scores: Sequence[int], labels: Sequence[bool], cutoff: int) -> Arm:
    declared = [index for index, value in enumerate(scores) if value >= cutoff]
    correct = sum(1 for index in declared if labels[index])
    positives = sum(1 for label in labels if label)
    return Arm(
        name=name, declared=len(declared), correct=correct,
        precision=correct / len(declared) if declared else None,
        recall=correct / positives if positives else 0.0,
        auc=exact_auc(scores, labels),
    )


def _discordant(left: Sequence[int], right: Sequence[int], labels: Sequence[bool],
                cutoff: int) -> tuple[int, int]:
    """Per-pair wins for the paired test: pairs exactly one arm called correctly.

    A call is correct when the declaration at the cutoff agrees with the pair's held-out
    status, so a false positive counts against an arm exactly as a miss does.
    """

    wins_left = wins_right = 0
    for here, there, label in zip(left, right, labels):
        right_here = (here >= cutoff) == bool(label)
        right_there = (there >= cutoff) == bool(label)
        wins_left += right_here and not right_there
        wins_right += right_there and not right_here
    return wins_left, wins_right


@dataclass(frozen=True)
class LinkPredictionResult:
    seed_provenance: str
    seed_size: int
    theta: float
    cutoff: int
    rounds: int
    mapping_size: int
    transferred_pairs: int
    held_out: int
    negatives: int
    deanonymization: Arm
    structure_only: Arm
    separability: dict[str, float | int | str | None]


def compare(target, auxiliary, seeds: Mapping[Vertex, Vertex], held_out: Iterable[Pair],
            negatives: Iterable[Pair], *, seed_provenance: str, theta: float = 1.5,
            cutoff: int = 2, min_correct_gain: int = 1,
            scorer=score) -> LinkPredictionResult:
    """Score the same pairs with and without the de-anonymized auxiliary view.

    `held_out` are target links removed from the view before propagation ran; `negatives` are
    pairs the target view does not join and never did.  Both must be absent from `target`, or
    the arms are being asked to predict something they can read off their own input.

    Both arms use `scorer`, so an ablation of the score changes the comparison and not one side
    of it.  Under the default the de-anonymization arm's score **dominates** the structure-only
    arm's on every pair — the transfer only ever adds neighbours — so its declaration set is a
    superset at any cutoff and its recall cannot come out lower.  That is a property of the
    construction and not a finding; what can and does invert is the AUC and the paired
    discordant count, because the arm pays for the extra declarations in false positives.

    `min_correct_gain` is the pre-registered effect for the paired comparison and the verdict
    is a *direction* only: "a" says the de-anonymization arm called pairs the structure-only
    arm got wrong, and says nothing about the level, which precision and recall carry.
    """

    held_out, negatives = list(held_out), list(negatives)
    pairs = held_out + negatives
    labels = [True] * len(held_out) + [False] * len(negatives)
    structure = neighbourhoods(target)
    for u, v in pairs:
        if v in structure.get(u, ()):
            raise ValueError(f"pair {(u, v)} is already an edge of the target view")

    prediction = predict(target, auxiliary, seeds, pairs, seed_provenance=seed_provenance,
                         theta=theta, scorer=scorer)
    deanon_scores = list(prediction.scores)
    structure_scores = [scorer(structure, u, v) for u, v in pairs]
    wins_deanon, wins_structure = _discordant(deanon_scores, structure_scores, labels, cutoff)
    verdict, p = separable(wins_deanon, wins_structure, wins_deanon - wins_structure,
                           min_correct_gain)
    return LinkPredictionResult(
        seed_provenance=seed_provenance, seed_size=len(seeds), theta=theta, cutoff=cutoff,
        rounds=prediction.rounds, mapping_size=len(prediction.mapping),
        transferred_pairs=prediction.transferred_pairs,
        held_out=len(held_out), negatives=len(negatives),
        deanonymization=_arm("deanonymization", deanon_scores, labels, cutoff),
        structure_only=_arm("structure_only", structure_scores, labels, cutoff),
        separability={"deanonymization_only": wins_deanon, "structure_only": wins_structure,
                      "min_correct_gain": min_correct_gain, "p": p,
                      "beats_structure_only": verdict},
    )
