"""Evaluation seam for the N--S baseline on contracted Bitcoin views.

The correspondence used for grading is deliberately kept separate from seed discovery.
An automatic seed is admitted only when an independently observed public entity label has
exactly one vertex in each view.  In particular, degree and the withheld correspondence
may select an evaluation population, but may not manufacture seeds.

Where a checkout holds no such label on both sides, the paper's own seed-assisted protocol
is still available: draw the seeds from the withheld correspondence itself.  Every result
therefore carries `seed_provenance`, because the two runs answer different questions.  A
run stamped ``SEED_SAMPLED`` measures how far propagation carries an identity it was
handed; it is never evidence that the identity could have been found, and reporting it as
an independent attack would be a false claim about the seeds, not about the algorithm.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Hashable, Iterable, Mapping

from .baselines.ns_social_attack import evaluate, propagate
from .reproducibility import separable

Vertex = Hashable

SEED_INDEPENDENT = "independent-entity-label"
SEED_SAMPLED = "withheld-correspondence-sample"


def unique_entity_seeds(
    left_labels: Iterable[tuple[str, Vertex]],
    right_labels: Iterable[tuple[str, Vertex]],
) -> dict[Vertex, Vertex]:
    """Return unambiguous cross-view seeds from independently detected entity names.

    Ambiguity is refused, never resolved, on both sides.  An entity holding more than one
    vertex in either view is dropped: repeated vertices are not guessed or paired by degree,
    which prevents the grading correspondence from leaking into the attack.  A *vertex*
    claimed by more than one entity is dropped for the same reason, and this is the ordinary
    case rather than the exotic one -- a co-spend cluster holding both a pool address and an
    exchange deposit address carries two entity labels on one contracted vertex.  Resolving
    such a collision by iteration order would silently drop one label on the left, and on the
    right would return a non-injective map that `propagate` rejects outright.

    The result is therefore a partial injection: every left vertex appears once, every right
    vertex appears once.
    """

    sides = []
    for observations in (left_labels, right_labels):
        grouped: dict[str, set[Vertex]] = defaultdict(set)
        for entity, vertex in observations:
            grouped[entity].add(vertex)
        sides.append(grouped)
    left, right = sides
    candidates = [
        (next(iter(vertices)), next(iter(right[entity])))
        for entity, vertices in left.items()
        if len(vertices) == 1 and len(right.get(entity, ())) == 1
    ]
    left_claims = Counter(u for u, _ in candidates)
    right_claims = Counter(v for _, v in candidates)
    return {u: v for u, v in candidates
            if left_claims[u] == 1 and right_claims[v] == 1}


def graph_overlap(left, right, truth: Mapping[Vertex, Vertex]) -> dict[str, float | int]:
    """Measure overlap of planted vertices and their directed relationships."""

    eligible = {u: v for u, v in truth.items()
                if u in left.vertices and v in right.vertices}
    left_edges = {(u, v) for (u, v) in left.edges if u in eligible and v in eligible}
    # Left-view edges whose image under the correspondence also exists in the right view: still
    # left-view pairs, which is why they are not named for the right side.
    recurring = {(u, v) for (u, v) in left_edges
                 if (eligible[u], eligible[v]) in right.edges}
    return {
        "vertices": len(eligible),
        "left_internal_edges": len(left_edges),
        "recurring_edges": len(recurring),
        "edge_overlap": len(recurring) / len(left_edges) if left_edges else 0.0,
    }


def eligible_correspondence(left, right, truth: Mapping[Vertex, Vertex]):
    """The part of the withheld correspondence both views can actually be graded on."""

    return {u: v for u, v in truth.items() if u in left.vertices and v in right.vertices}


def sampled_seeds(truth: Mapping[Vertex, Vertex], fraction: float, rng) -> dict[Vertex, Vertex]:
    """Draw a seed set from the withheld correspondence at `fraction` of its population.

    This is grading information handed to the attack, so a run using it must record
    ``SEED_SAMPLED``.  Sampling is uniform rather than by degree: taking the highest-degree
    correspondences would seed exactly the vertices propagation finds easiest and report the
    resulting spread as the algorithm's reach.
    """

    keys = sorted(truth, key=repr)
    count = max(2, round(len(keys) * fraction))
    return {u: truth[u] for u in rng.sample(keys, min(count, len(keys)))}


def _shuffle_images(seeds: Mapping[Vertex, Vertex], rng) -> dict[Vertex, Vertex]:
    """The falsification control: the same seed vertices, wrong images.

    A uniform shuffle of a small seed set can return the identity, and an identity "control"
    is the attack run twice.  Redraw until the permutation moves something; the reported
    `fixed_points` says how much of the seed set it still left in place.
    """

    images = list(seeds.values())
    for _ in range(16):
        rng.shuffle(images)
        shuffled = dict(zip(seeds, images))
        if shuffled != dict(seeds):
            return shuffled
    return dict(zip(seeds, images))


def _placement(mapping: Mapping[Vertex, Vertex], truth: Mapping[Vertex, Vertex],
               seeds) -> dict[str, float | int | None]:
    """Where the declarations landed.

    Two different failures hide behind one precision figure: naming the wrong image for a
    vertex that has one, and naming any image at all for a vertex the other view does not
    contain.  The algorithm has no abstention for the second, and on disjoint observation
    windows most of a view is in that class, so the split has to be reported.

    `precision_where_an_image_exists` is a *diagnostic, not an operating point*: the subgroup
    is selected by membership in the withheld correspondence, which the attacker does not
    have, so no thresholding available to it can reach that number.  It says where the signal
    is, and must never be quoted as the attack's precision.
    """

    declared = [u for u in mapping if u not in seeds]
    gradeable = [u for u in declared if u in truth]
    return {
        "declared_with_an_image": len(gradeable),
        "precision_where_an_image_exists": (
            sum(mapping[u] == truth[u] for u in gradeable) / len(gradeable)
            if gradeable else None),
    }


def _discordant(attack: Mapping[Vertex, Vertex], control: Mapping[Vertex, Vertex],
                truth: Mapping[Vertex, Vertex], seeds) -> tuple[int, int]:
    """Per-vertex wins for the paired test: cases where exactly one arm was right."""

    wins_attack = wins_control = 0
    for node, image in truth.items():
        if node in seeds:
            continue
        right_here, right_there = attack.get(node) == image, control.get(node) == image
        wins_attack += right_here and not right_there
        wins_control += right_there and not right_here
    return wins_attack, wins_control


@dataclass(frozen=True)
class BitcoinNSResult:
    seed_provenance: str
    seed_size: int
    seed_fraction: float
    overlap: dict[str, float | int]
    attack: dict[str, float | int | None]
    shuffled_seed_control: dict[str, float | int | None]
    seed_only_control: dict[str, float | int | None]
    separability: dict[str, float | int | str | None]
    theta: float
    rounds: int
    accepted_per_round: tuple[int, ...]
    shuffled_accepted_per_round: tuple[int, ...]


def run_bitcoin_views(left, right, truth: Mapping[Vertex, Vertex],
                      seeds: Mapping[Vertex, Vertex], *, theta=1.5, rng_seed=0,
                      seed_provenance: str = SEED_INDEPENDENT, min_correct_gain: int = 1):
    """Run faithful propagation and two controls against the withheld correspondence.

    `min_correct_gain` is the pre-registered effect for the paired shuffled-seed comparison:
    the direction under test is "the attack recovers at least this many correspondences the
    shuffled-seed control does not".  It is a direction claim only — a verdict of "a" says
    the spread is not an artifact of the seed positions, and says nothing about precision,
    which the reported levels have to carry on their own.
    """

    truth = eligible_correspondence(left, right, truth)
    seeds = dict(seeds)
    if any(truth.get(u) != v for u, v in seeds.items()):
        raise ValueError("supplied seed conflicts with the withheld correspondence")

    result = propagate(left, right, seeds, theta=theta)
    attack = evaluate(result.mapping, truth, seeds)
    attack.update(_placement(result.mapping, truth, seeds))

    shuffled = _shuffle_images(seeds, random.Random(rng_seed))
    shuffled_result = propagate(left, right, shuffled, theta=theta)
    shuffled_metrics = evaluate(shuffled_result.mapping, truth, seeds)
    shuffled_metrics.update(_placement(shuffled_result.mapping, truth, seeds))
    shuffled_metrics["fixed_points"] = sum(shuffled[u] == v for u, v in seeds.items())

    # With no propagation, a held-out node can never be declared.  Keep this explicit so
    # reports do not compare the attack to a seed count disguised as recovered identity.
    seed_only = evaluate(seeds, truth, seeds)

    wins_attack, wins_shuffled = _discordant(result.mapping, shuffled_result.mapping,
                                             truth, seeds)
    verdict, p = separable(wins_attack, wins_shuffled, wins_attack - wins_shuffled,
                           min_correct_gain)
    return BitcoinNSResult(
        seed_provenance=seed_provenance, seed_size=len(seeds),
        seed_fraction=len(seeds) / len(truth) if truth else 0.0,
        overlap=graph_overlap(left, right, truth),
        attack=attack, shuffled_seed_control=shuffled_metrics,
        seed_only_control=seed_only,
        separability={"attack_only": wins_attack, "shuffled_only": wins_shuffled,
                      "min_correct_gain": min_correct_gain, "p": p, "beats_shuffled": verdict},
        theta=theta, rounds=result.rounds,
        accepted_per_round=result.accepted_per_round,
        shuffled_accepted_per_round=shuffled_result.accepted_per_round,
    )


def sweep_bitcoin_views(left, right, truth: Mapping[Vertex, Vertex], fractions, thetas, *,
                        rng_seed=0, min_correct_gain=1):
    """The seed-assisted sweep: one run per (seed fraction, theta), seeds drawn from the
    withheld correspondence.

    theta is part of the reported configuration, not a dial turned until a number appears, so
    every value swept is reported whether or not anything propagated under it.
    """

    truth = eligible_correspondence(left, right, truth)
    rows = []
    for fraction in fractions:
        seeds = sampled_seeds(truth, fraction, random.Random(rng_seed))
        for theta in thetas:
            rows.append(run_bitcoin_views(left, right, truth, seeds, theta=theta,
                                          rng_seed=rng_seed, seed_provenance=SEED_SAMPLED,
                                          min_correct_gain=min_correct_gain))
    return rows
