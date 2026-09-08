"""Does the cross-view matcher beat degree alone, and does it know which answers are good.

Two questions the framework's own criterion turns on, and both were measured on a slice that no
longer exists. The framework does not rest its case on coverage — it says high-confidence links can
feed other clustering heuristics — so the quantities that matter are whether precision rises with
the matcher's own confidence, and whether any of it survives the comparison to reading degrees off
the two views.

A shuffle control excludes chance and nothing else. The likelier alternative is that a matcher on a
degree-labelled graph recovers degree: a vertex of degree 47 in one view and one of degree 47 in the
other are an obvious pair with no propagation at all. The decisive control is therefore the exact
degree-class expectation — one over the number of B-vertices sharing the true partner's degree —
which is deliberately generous, since it is handed the true partner's degree that a degree-only
adversary would have to guess.

The harness is the framework's complete-clustering premise: both views hold the same pseudonyms and
only view B's labels are hidden, so the population is known and the correspondence is not. That is a
weaker premise than the split-cluster rejoin measured beside it (`graph-rejoin-2016-v1`), and the
difference is the point — this is what the matcher does when it is told which vertices to match.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

from .. import epoch_graph as eg
from ..contraction import PseudonymGraph, contract, contract_degrees
from ..result_artifacts import canonical_json_bytes, write_canonical_json
from ..scale_cluster import cluster_scale_np_stream
from ..view_match import ViewMatcher

EXPERIMENT_ID = "match-controls-v1"
DEFAULT_EPOCHS = ("data/epochs-2016-weekly-v1/391104-392111.epochgraph.xz",
                  "data/epochs-2016-weekly-v1/392112-393119.epochgraph.xz")
SEED_SHARES = (0.05, 0.10)
BANDS = (1.0, 2.0, 3.0, 5.0, 10.0)
MIN_DEGREE = 2
# The band a seed can do work from. Propagation refuses to route through a matched neighbour whose
# image exceeds the matcher's hub cap, so a hub handed over as a seed is evidence the matcher will
# not read; and a vertex below three neighbours has too thin a neighbourhood to identify anyone.
# Seeding by raw degree spends the whole budget on exactly the vertices that carry nothing.
SEEDABLE = (3, 100)


class VerificationError(ValueError):
    """The stored result differs from a fresh execution."""


def _addresses(path):
    found = set()
    for record in eg.decode(path):
        found.update(eg.in_addresses(record))
        found.update(eg.out_addresses(record))
    return found


def _active(path, lookup):
    stream = lambda: ((record, 0) for record in eg.decode(path))
    degrees = contract_degrees(stream(), lookup=lookup)
    keep = {vertex for vertex, degree in degrees.items() if degree >= MIN_DEGREE}
    graph = contract(stream(), lookup=lookup, axes=False, keep=keep)
    return graph, {vertex: degrees[vertex] for vertex in keep}


def _pseudonymise(graph, rng):
    """Relabel a view with opaque ids: the population stays visible, the correspondence does not.

    The source graph is consumed as it is copied. Holding both at full size doubles the peak on a
    view of this width, which is enough to be killed for memory rather than merely be slow.
    """
    names = sorted(graph.vertices, key=repr)
    rng.shuffle(names)
    sigma = {vertex: f"p{index}" for index, vertex in enumerate(names)}
    del names
    hidden = PseudonymGraph(axes=False)
    while graph.vertices:
        vertex, record = graph.vertices.popitem()
        hidden.vertices[sigma[vertex]] = record
    while graph.edges:
        (src, dst), edge = graph.edges.popitem()
        hidden.edges[(sigma[src], sigma[dst])] = edge
        hidden._out[sigma[src]].add(sigma[dst])
        hidden._in[sigma[dst]].add(sigma[src])
    graph._out.clear()
    graph._in.clear()
    return hidden, sigma


def _bands(graded, confidence, truth):
    """Precision by the eccentricity the match won by, against the degree-class expectation.

    `truth` maps a vertex to its image and the size of that image's degree class, so a guess is
    scored against the first and the baseline is one over the second.

    A match with only one materialised candidate is recorded with infinite eccentricity — the gate
    is skipped rather than computed, which `view_match` declares as a divergence from the paper.
    Those clear every floor, so a high band silently mixes "stood clear of its rivals" with "had
    none". The count is carried per row so the top band can be read for what it is.
    """
    rows = []
    for floor in (0.0,) + BANDS:
        kept = [u for u in graded if confidence[u][0] >= floor]
        correct = sum(1 for u in kept if graded[u] == truth[u][0])
        expectation = [1.0 / truth[u][1] for u in kept]
        rows.append({
            "eccentricity_at_least": floor,
            "matched": len(kept),
            "correct": correct,
            "uncontested": sum(1 for u in kept if confidence[u][0] == float("inf")),
            "precision": round(correct / len(kept), 6) if kept else None,
            "degree_class_expectation":
                round(sum(expectation) / len(expectation), 6) if expectation else None,
        })
    return rows


def build_artifact(epochs=DEFAULT_EPOCHS, seed=0):
    left, right = (Path(path) for path in epochs)
    counts = [sum(1 for _ in eg.decode(path)) for path in (left, right)]
    clustering = cluster_scale_np_stream(record for path in (left, right)
                                         for record in eg.decode(path))
    lookup = clustering.map_many(_addresses(left))
    lookup.update(clustering.map_many(_addresses(right)))
    del clustering

    graph_a, stat_a = _active(left, lookup)
    graph_b, stat_b = _active(right, lookup)
    del lookup

    rng = random.Random(seed)
    hidden, sigma = _pseudonymise(graph_b, rng)
    # `keep` admits a vertex on its degree, but contraction drops one whose counterparties
    # were all dropped, so the degree map is the wider of the two.
    stat_hidden = {sigma[vertex]: degree for vertex, degree in stat_b.items()
                   if vertex in sigma}
    del graph_b, stat_b

    # A vertex is matchable when both views hold it with an edge; degree is read on the hidden view
    # because that is the population a degree-only adversary would be choosing among.
    by_degree = Counter(hidden.degree(vertex) for vertex in hidden.vertices)
    matchable = [vertex for vertex in graph_a.vertices
                 if vertex in sigma and graph_a.degree(vertex) and hidden.degree(sigma[vertex])]
    truth = {vertex: (sigma[vertex], by_degree[hidden.degree(sigma[vertex])])
             for vertex in matchable}

    low, high = SEEDABLE
    seedable = [v for v in matchable
                if low <= graph_a.degree(v) <= high and low <= hidden.degree(sigma[v]) <= high]
    ordered = sorted(seedable, key=lambda v: (-(graph_a.degree(v) + hidden.degree(sigma[v])),
                                              repr(v)))
    arms, banded = [], {}
    for share in SEED_SHARES:
        count = max(2, int(len(ordered) * share))
        # Iterate the ranked list, not a set built from it. The seeded mapping does not care — a
        # mapping is its content — but the shuffled control is built by permuting
        # `supplied.values()`, so a set's iteration order decides which image each seed is wrongly
        # given, and Python randomises that per process. The control arm then differs between two
        # runs of the same input, which is exactly how this was found.
        chosen = ordered[:count]
        seeds = set(chosen)
        supplied = {vertex: sigma[vertex] for vertex in chosen}
        images = list(supplied.values())
        rng.shuffle(images)
        shuffled = dict(zip(supplied, images))
        for label, mapping in (("seeded", supplied), ("shuffled", shuffled)):
            matcher = ViewMatcher()
            matched = matcher.match(graph_a, hidden, dict(mapping),
                                    stat_a=stat_a, stat_b=stat_hidden)
            graded = {u: w for u, w in matched.items() if u in truth and u not in seeds}
            correct = sum(1 for u, w in graded.items() if w == truth[u][0])
            arms.append({"seed_share": share, "seeds": count, "arm": label,
                         "guesses": len(graded), "correct": correct,
                         "precision": round(correct / len(graded), 6) if graded else None})
            if label == "seeded":
                banded[f"{share:g}"] = _bands(graded, matcher.confidence,
                                              {u: truth[u] for u in graded})

    sizes = sorted(truth[vertex][1] for vertex in matchable)
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "datasets": [f"epoch-graph-2016-{Path(p).name.split('.')[0]}-v1" for p in epochs],
        "population": {
            # The file names, not the paths given: a cold-start reproduction reads the
            # datasets from wherever the bundle materialized them, and a path recorded
            # here would make the artifact differ by where it was run.
            "views": [left.name, right.name],
            "transactions": counts,
            "vertices": [len(graph_a.vertices), len(hidden.vertices)],
            "matchable_in_both_views": len(matchable),
            "seedable": len(seedable),
            "degree_class_size_median": sizes[len(sizes) // 2] if sizes else 0,
            "degree_class_size_max": sizes[-1] if sizes else 0,
        },
        "matching": arms,
        "confidence": banded,
    }


def load_artifact(path):
    try:
        with Path(path).open(encoding="utf-8") as source:
            value = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerificationError("artifact root must be an object")
    return value


def verify_artifact(artifact, epochs=DEFAULT_EPOCHS):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported match-controls artifact identity")
    measured = build_artifact(epochs)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def _widest(artifact):
    return max(artifact["confidence"], key=float)


def render_markdown(artifact):
    population = artifact["population"]
    widest = _widest(artifact)
    bands = artifact["confidence"][widest]
    overall, narrowest = bands[0], bands[-1]
    lines = [
        "# Does the matcher beat degree alone",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"Two consecutive 2016 weekly windows of {population['transactions'][0]:,} and "
        f"{population['transactions'][1]:,} transactions, contracted into "
        f"{population['vertices'][0]:,} and {population['vertices'][1]:,} pseudonyms. View B's "
        f"labels are hidden, so {population['matchable_in_both_views']:,} vertices are known to be "
        f"present in both views and the correspondence between them is not. Seeds are drawn from "
        f"the {population['seedable']:,} of those whose degree sits in "
        f"[{SEEDABLE[0]}, {SEEDABLE[1]}] on both sides — below that a neighbourhood identifies "
        f"nobody, and above it propagation refuses to route through the vertex at all, so a seed "
        f"outside the band is a seed the matcher cannot spend.",
        "",
        f"At the {float(widest):.0%} seeding, precision against the eccentricity each match won by:",
        "",
        "| eccentricity | matched | uncontested | correct | precision | degree class alone | "
        "margin |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in bands:
        precision = row["precision"]
        baseline = row["degree_class_expectation"]
        margin = ("—" if precision is None or baseline is None
                  else f"{precision - baseline:+.3f}")
        lines.append(
            f"| ≥ {row['eccentricity_at_least']:g} | {row['matched']} | {row['uncontested']} | "
            f"{row['correct']} | {'—' if precision is None else f'{precision:.3f}'} | "
            f"{'—' if baseline is None else f'{baseline:.5f}'} | {margin} |")
    lines.extend([
        "",
        f"**The matcher beats degree, and least where it is most sure.** Overall it is "
        f"{overall['precision'] - overall['degree_class_expectation']:+.3f} against what degree "
        f"alone is worth. That margin does not widen as the matcher grows confident; it collapses, "
        f"to {narrowest['precision'] - narrowest['degree_class_expectation']:+.3f} at eccentricity "
        f"{narrowest['eccentricity_at_least']:g}. Precision does rise with confidence "
        f"({overall['precision']:.3f} to {narrowest['precision']:.3f}), which is the property the "
        f"framework's argument wants — but the degree baseline rises faster "
        f"({overall['degree_class_expectation']:.3f} to "
        f"{narrowest['degree_class_expectation']:.3f}), because the matches the matcher is surest "
        f"of are the ones whose partner has a rare degree. The high-confidence band is where the "
        f"matcher is *hardest* to distinguish from reading the degrees off.",
        "",
        "The uncontested column is the matches where only one candidate materialised at all. The "
        "matcher records those with infinite eccentricity and skips the gate rather than computing "
        "it, so they clear every floor: a high band is only evidence about *standing clear of "
        "rivals* to the extent it is not made of them.",
        "",
        "The degree-class column is what degree is worth with no algorithm attached: one over the "
        "number of B-vertices sharing the true partner's degree. It is handed that degree, which a "
        "degree-only adversary would have to guess, so it bounds such an adversary from above rather "
        f"than approximating one. Classes here run to {population['degree_class_size_max']:,} "
        f"vertices with a median of {population['degree_class_size_median']}.",
        "",
        "Every arm, with the shuffled-seed control beside each seeded one:",
        "",
        "| seed share | arm | seeds | guesses | correct | precision |",
        "|---:|---|---:|---:|---:|---:|",
    ])
    for row in artifact["matching"]:
        precision = row["precision"]
        lines.append(
            f"| {row['seed_share']:.0%} | {row['arm']} | {row['seeds']} | {row['guesses']} | "
            f"{row['correct']} | {'—' if precision is None else f'{precision:.3f}'} |")
    lines.extend([
        "",
        f"The seeded arm returns {overall['matched']} graded matches. A shuffled seed is the same "
        "matcher on the same graphs with the correspondence destroyed, and what it returns is the "
        "share of this that survives without the seeds meaning anything.",
        "",
        "This is the complete-clustering premise: the matcher is told which vertices appear in both "
        "views and asked only which is which. The split-cluster premise, where a straddling entity "
        "carries a separate pseudonym per view and the matcher must discover that they are one, is "
        "measured beside it (`results/generated/graph-rejoin-2016-v1.md`) and is the harder question.",
        "",
        "Cluster membership is a co-spend relation rather than observed wallet ownership, the seeds "
        "are supplied, and this is two windows of one era. None of it is a privacy score.",
        "",
        "## Reproducibility / provenance",
        "",
        "State 1 in `results/REPRODUCIBILITY.md`: band-pinned on committed data — the artifact is "
        "recomputed from the committed weekly epoch graphs and compared byte for byte.",
    ])
    return "\n".join(lines) + "\n"


def _parser():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("reproduce", "verify"))
    parser.add_argument("--epochs", nargs=2, default=list(DEFAULT_EPOCHS))
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--markdown", required=True)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    if args.command == "reproduce":
        artifact = build_artifact(tuple(args.epochs))
        write_canonical_json(args.artifact, artifact)
        destination = Path(args.markdown)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_markdown(artifact), encoding="utf-8")
    else:
        artifact = verify_artifact(load_artifact(args.artifact), tuple(args.epochs))
        if Path(args.markdown).read_text(encoding="utf-8") != render_markdown(artifact):
            raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
