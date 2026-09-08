"""Rejoining a cluster split across two weekly views, on committed transactions.

The measurements this replaces were taken on a 1.1 GB slice that no longer exists, so nobody could
check them and nobody could take them again. The committed weekly graph carries the same object at
seven times the size: two consecutive windows, every cluster that straddles their boundary
contracted under a separate pseudonym on each side, and a matcher asked to rejoin the two halves
from structure alone.

Two things make the answer readable rather than merely low. The seeds are handed to the matcher, so
this measures propagation given a foothold rather than an attack that finds one; and a shuffled-seed
arm runs beside every seeded arm, so a guess rate that survives the shuffle is the graph answering
the seeds rather than the matcher answering itself.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from .. import epoch_graph as eg
from ..contraction import contract, contract_degrees
from ..graph_shape import summary as shape_summary
from ..result_artifacts import canonical_json_bytes, write_canonical_json
from ..scale_cluster import cluster_scale_np_stream
from ..view_match import ViewMatcher
from ..views import split_clusters_by_view, view_lookup

EXPERIMENT_ID = "graph-rejoin-2016-v1"
DEFAULT_EPOCHS = ("data/epochs-2016-weekly-v1/391104-392111.epochgraph.xz",
                  "data/epochs-2016-weekly-v1/392112-393119.epochgraph.xz")
SEED_SHARES = (0.05, 0.10)
MIN_DEGREE = 2


class VerificationError(ValueError):
    """The stored result differs from a fresh execution."""


def _addresses(path):
    found = set()
    for record in eg.decode(path):
        found.update(eg.in_addresses(record))
        found.update(eg.out_addresses(record))
    return found


def _active(path, lookup):
    """Contract one view, keeping the vertices a matcher could route through."""
    stream = lambda: ((record, 0) for record in eg.decode(path))
    degrees = contract_degrees(stream(), lookup=lookup)
    keep = {vertex for vertex, degree in degrees.items() if degree >= MIN_DEGREE}
    graph = contract(stream(), lookup=lookup, axes=False, keep=keep)
    return graph, {vertex: degrees[vertex] for vertex in keep}


def build_artifact(epochs=DEFAULT_EPOCHS, seed=0):
    left, right = (Path(path) for path in epochs)
    counts = [sum(1 for _ in eg.decode(path)) for path in (left, right)]
    clustering = cluster_scale_np_stream(record for path in (left, right)
                                         for record in eg.decode(path))
    left_addresses = _addresses(left)
    lookup = clustering.map_many(left_addresses)
    lookup.update(clustering.map_many(_addresses(right)))
    del clustering

    split, origin = split_clusters_by_view(lookup, left_addresses, frac=1.0,
                                           rng=random.Random(seed))
    del left_addresses
    graph_a, stat_a = _active(left, view_lookup(lookup, split, "#a"))
    graph_b, stat_b = _active(right, view_lookup(lookup, split, "#b"))
    del lookup

    right_side = {v for v in graph_b.vertices if isinstance(v, str) and v.endswith("#b")}
    truth = {u: f"{origin[u]}#b" for u in graph_a.vertices
             if isinstance(u, str) and u.endswith("#a") and f"{origin[u]}#b" in right_side}
    straddlers = set(truth)
    internal = {u: sum(1 for n in graph_a.neighbours(u) if n in straddlers) for u in straddlers}

    shapes = [{k: (round(v, 6) if isinstance(v, float) else v)
               for k, v in shape_summary(g, rng=random.Random(seed)).items()}
              for g in (graph_a, graph_b)]
    ordered = sorted(truth, key=lambda u: -(graph_a.degree(u) + graph_b.degree(truth[u])))
    rng = random.Random(seed)
    arms = []
    for share in SEED_SHARES:
        count = max(2, int(len(ordered) * share))
        seeds = set(ordered[:count])
        supplied = {u: truth[u] for u in seeds}
        images = list(supplied.values())
        rng.shuffle(images)
        shuffled = dict(zip(supplied, images))
        for directional in (False, True):
            for label, mapping in (("seeded", supplied), ("shuffled", shuffled)):
                matched = ViewMatcher(revisit=True, directional=directional,
                                      min_common=4).match(graph_a, graph_b, mapping,
                                                          stat_a=stat_a, stat_b=stat_b)
                guesses = {u: w for u, w in matched.items() if u in truth and u not in seeds}
                correct = sum(1 for u, w in guesses.items() if w == truth[u])
                arms.append({
                    "seed_share": share, "seeds": count,
                    "matcher": "directed" if directional else "undirected",
                    "arm": label, "guesses": len(guesses), "correct": correct,
                    "precision": round(correct / len(guesses), 6) if guesses else None,
                })
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "datasets": [f"epoch-graph-2016-{Path(p).name.split('.')[0]}-v1" for p in epochs],
        "population": {
            "views": [str(left), str(right)],
            "transactions": counts,
            "pairs_to_rejoin": len(truth),
            "non_seed_pairs_at_widest_seeding":
                len(truth) - max(int(len(ordered) * share) for share in SEED_SHARES),
            "mean_internal_degree": round(sum(internal.values()) / len(straddlers), 6)
            if straddlers else 0.0,
        },
        "shape": shapes,
        "matching": arms,
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
        raise VerificationError("unsupported graph-rejoin artifact identity")
    measured = build_artifact(epochs)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    population = artifact["population"]
    lines = [
        "# Rejoining a cluster split across two weekly views",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"Two consecutive 2016 weekly windows of {population['transactions'][0]:,} and "
        f"{population['transactions'][1]:,} transactions. {population['pairs_to_rejoin']:,} clusters straddle "
        f"the boundary and survive contraction in both views, at a mean internal degree of "
        f"{population['mean_internal_degree']:.3f}.",
        "",
        "| statistic | view A | view B |",
        "|---|---:|---:|",
    ]
    for field in ("vertices", "edges", "mean_degree", "degree_1_share", "transitivity",
                  "configuration_transitivity", "assortativity", "tail_exponent"):
        left_value, right_value = (s[field] for s in artifact["shape"])
        fmt = (lambda v: "—" if v is None else f"{v:,}" if isinstance(v, int) else f"{v:.4f}")
        lines.append(f"| {field.replace('_', ' ')} | {fmt(left_value)} | {fmt(right_value)} |")
    left, right = artifact["shape"]
    lines.extend([
        "",
        f"The framework's premise is that a contracted view is a social network in the sense its "
        f"matching algorithm needs. On this measurement it is not, on the two axes that decide it. "
        f"Clustering sits at {left['transitivity']:.4f} and {right['transitivity']:.4f} against a "
        f"configuration-model null of {left['configuration_transitivity']:.4f} and "
        f"{right['configuration_transitivity']:.4f} — the degree distribution alone would produce "
        f"far more triangles than the graph has. Degree correlation is "
        f"{left['assortativity']:+.4f} and {right['assortativity']:+.4f}: hubs attach to leaves, "
        f"which is what transaction graphs do and the opposite of what a social graph does. A "
        f"matcher that routes through a vertex's neighbourhood is asking that neighbourhood to be "
        f"distinctive and stable, and neither statistic says it is.",
        "",
        "| seed share | matcher | arm | guesses | correct | precision |",
        "|---:|---|---|---:|---:|---:|",
    ])
    for row in artifact["matching"]:
        precision = "—" if row["precision"] is None else f"{row['precision']:.3f}"
        lines.append(f"| {row['seed_share']:.0%} | {row['matcher']} | {row['arm']} | "
                     f"{row['guesses']} | {row['correct']} | {precision} |")
    seeded = [r for r in artifact["matching"] if r["arm"] == "seeded"]
    shuffled = [r for r in artifact["matching"] if r["arm"] == "shuffled"]
    lines.extend([
        "",
        f"At the widest seeding the matcher is offered "
        f"{population['pairs_to_rejoin'] - max(r['seeds'] for r in artifact['matching']):,} "
        f"non-seed pairs. Across every seeded arm it guesses "
        f"{sum(r['guesses'] for r in seeded)} and gets {sum(r['correct'] for r in seeded)} right; "
        f"the shuffled-seed arms guess {sum(r['guesses'] for r in shuffled)}. A cascade that "
        f"carried itself would show each seed unlocking more than itself, and it does not at these "
        f"view widths. One match is not ignition, and it is a different statement from none.",
        "",
        "Cluster membership here is a co-spend relation rather than observed wallet ownership, and "
        "the seeds are supplied. The result is what propagation does once a foothold exists, not "
        "whether one can be found.",
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
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--markdown", required=True)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    if args.command == "reproduce":
        artifact = build_artifact()
        write_canonical_json(args.artifact, artifact)
        destination = Path(args.markdown)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_markdown(artifact), encoding="utf-8")
    else:
        artifact = verify_artifact(load_artifact(args.artifact))
        if Path(args.markdown).read_text(encoding="utf-8") != render_markdown(artifact):
            raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
