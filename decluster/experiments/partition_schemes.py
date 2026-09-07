"""Compare the partition schemes the framework names, on data a reader has.

The framework calls the temporal cut its own trivial example and asks for one that divides along
cluster-collapse regions instead, generalised to n views. Both are implemented, and
`results/RESULTS-partition-cuts.md` reports the comparison over 300,000 transactions, and for a
while that measurement rested on a 977 MB export nobody else held. It did not need the whole
export: the run consumes one prefix, and that prefix recompresses to 50 MB, so it is committed and
this reproduces the published table rather than approximating it.

The number that decides the comparison is not the straddler count but the connectivity among them
— propagation needs edges *between* straddlers, not merely a population of them — which is why the
run reports mean straddler degree beside the count.
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
from pathlib import Path

from .. import contraction, tx_addrs, view_partition, views
from ..result_artifacts import canonical_json_bytes, write_canonical_json
from ..view_match import ViewMatcher

EXPERIMENT_ID = "partition-schemes-v1"
DEFAULT_DATASET = "data/partition-cuts-300k-2016.ndjson.gz"
SCHEMES = ("epoch", "decore", "collapse")
VIEW_COUNTS = (2, 3, 4)
CORE_FRACTION = 0.01
MIN_SIDE = 2
SEED = 0
SEED_SHARES = (0.05, 0.10)


class VerificationError(ValueError):
    """The dataset or stored result violates this experiment's contract."""


def _load(path):
    sample = []
    try:
        with gzip.open(path, "rt", encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                transaction = json.loads(line)
                if not isinstance(transaction, dict) or not transaction.get("txid"):
                    raise VerificationError(
                        f"{path}:{line_number}: transaction must be an object with a txid"
                    )
                sample.append((transaction, 0))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read slice snapshot {path}: {exc}") from exc
    if not sample:
        raise VerificationError(f"slice snapshot is empty: {path}")
    return sample


def _active(sample, indices, lookup):
    degrees = contraction.contract_degrees(sample, indices=indices, lookup=lookup)
    keep = {vertex for vertex, degree in degrees.items() if degree >= 2}
    graph = contraction.contract(sample, indices=indices, lookup=lookup, axes=False, keep=keep)
    return graph, {vertex: degrees[vertex] for vertex in keep}


def _straddlers(sample, lookup, parts):
    addresses = set()
    for index in parts[0]:
        transaction = sample[index][0]
        addresses.update(tx_addrs.in_addrs(transaction))
        addresses.update(address for address, _ in tx_addrs.out_addrs(transaction))
    split, origin = views.split_clusters_by_view(
        lookup, addresses, frac=1.0, rng=random.Random(SEED)
    )
    left, stat_left = _active(sample, parts[0], views.view_lookup(lookup, split, "#a"))
    right, stat_right = _active(sample, parts[1], views.view_lookup(lookup, split, "#b"))
    in_right = {v for v in right.vertices if isinstance(v, str) and v.endswith("#b")}
    truth = {
        vertex: f"{origin[vertex]}#b"
        for vertex in left.vertices
        if isinstance(vertex, str) and vertex.endswith("#a") and f"{origin[vertex]}#b" in in_right
    }
    return left, right, stat_left, stat_right, truth


def _scheme(sample, lookup, scheme):
    parts = view_partition.partition_coins(sample, scheme=scheme, core_frac=CORE_FRACTION,
                                  n_views=2, min_side=MIN_SIDE)
    boundary = len(sample) - sum(len(part) for part in parts)
    left, right, stat_left, stat_right, truth = _straddlers(sample, lookup, parts[:2])
    crowd = set(truth)
    among = sum(1 for source, destination in left.edges
                if source in crowd and destination in crowd)
    connected = sum(1 for vertex in crowd
                    if any(other in crowd for other in left.neighbours(vertex)))
    degree = (sum(1 for v in crowd for other in left.neighbours(v) if other in crowd)
              / len(crowd)) if crowd else 0.0
    ranked = sorted(truth, key=lambda v: -(left.degree(v) + right.degree(truth[v])))
    seeded = []
    for share in SEED_SHARES:
        count = max(2, int(len(ranked) * share))
        seeds = set(ranked[:count])
        matched = ViewMatcher(revisit=True).match(
            left, right, {v: truth[v] for v in seeds}, stat_a=stat_left, stat_b=stat_right
        )
        guesses = {v: w for v, w in matched.items() if v in truth and v not in seeds}
        correct = sum(1 for v, w in guesses.items() if w == truth[v])
        remaining = len(truth) - len(seeds)
        seeded.append({
            "seed_share": share, "seeds": len(seeds), "guesses": len(guesses),
            "correct": correct,
            "precision": (correct / len(guesses)) if guesses else None,
            "recall": (correct / remaining) if remaining > 0 else None,
        })
    return {
        "scheme": scheme,
        "view_sizes": [len(part) for part in parts],
        "boundary_transactions": boundary,
        "straddling_entities": len(truth),
        "edges_among_straddlers": among,
        "mean_straddler_degree": degree,
        "straddlers_with_a_straddling_neighbour": connected,
        "seeded": seeded,
    }


def build_artifact(dataset=DEFAULT_DATASET):
    sample = _load(dataset)
    lookup = views.cluster_addresses(sample, refuse=True)
    rows = [_scheme(sample, lookup, scheme) for scheme in SCHEMES]
    generalisation = {
        scheme: {
            str(count): [len(part) for part in view_partition.partition_coins(
                sample, scheme=scheme, core_frac=CORE_FRACTION, n_views=count, min_side=MIN_SIDE)]
            for count in VIEW_COUNTS
        }
        for scheme in SCHEMES
    }
    by_scheme = {row["scheme"]: row for row in rows}
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "dataset": "slice-a-channels-2016-v1",
        "measurement": {
            "transactions": len(sample),
            "clusters": len(set(lookup.values())),
            "schemes": rows,
            "view_counts": generalisation,
            "collapse_costs_over_epoch": (
                by_scheme["collapse"]["boundary_transactions"]
                - by_scheme["epoch"]["boundary_transactions"]
            ),
            "any_scheme_ignited_the_matcher": any(
                seed["guesses"] for row in rows for seed in row["seeded"]
            ),
        },
        "parameters": {
            "schemes": list(SCHEMES),
            "view_counts": list(VIEW_COUNTS),
            "core_fraction": CORE_FRACTION,
            "min_side": MIN_SIDE,
            "seed": SEED,
            "seed_shares": list(SEED_SHARES),
        },
        "limitations": [
            "the matcher recovers a handful of pairs at best, so the comparison rests on the "
            "straddler subgraph rather than on precision",
            "one slice, one era, one 300,000-transaction prefix",
            "cluster membership is a co-spend label, not wallet ownership",
            "the export carries addresses but no values, so the collapse detector sees only the "
            "shape rule and never the de-mix arm",
            "the result is not a privacy score",
        ],
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


def verify_artifact(artifact, dataset=DEFAULT_DATASET):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported partition-scheme artifact identity")
    measured = build_artifact(dataset)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    measured = artifact["measurement"]
    rows = {row["scheme"]: row for row in measured["schemes"]}
    lines = [
        "# Which cut makes two matchable views",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"{measured['transactions']} transactions, {measured['clusters']} clusters. Each scheme "
        "cuts the slice into two views, a straddling entity gets a distinct pseudonym per view, "
        "and the matcher has to rejoin them from structure alone.",
        "",
        "| scheme | boundary txs | pairs to rejoin | straddler edges | mean straddler degree | "
        "non-isolated | correct @ 10% seed |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for scheme in ("epoch", "decore", "collapse"):
        row = rows[scheme]
        share = (100.0 * row["straddlers_with_a_straddling_neighbour"] / row["straddling_entities"]
                 if row["straddling_entities"] else 0.0)
        at_ten = next(s for s in row["seeded"] if s["seed_share"] == 0.10)
        cost = (100.0 * row["boundary_transactions"] / measured["transactions"])
        lines.append(
            f"| `{scheme}` | {row['boundary_transactions']} ({cost:.1f}%) | "
            f"{row['straddling_entities']} | {row['edges_among_straddlers']} | "
            f"{row['mean_straddler_degree']:.2f} | {share:.1f}% | {at_ten['correct']} |"
        )
    epoch, decore, collapse = rows["epoch"], rows["decore"], rows["collapse"]
    lines += [
        "",
        f"**`decore` cuts the wrong thing.** Dropping the busiest "
        f"{artifact['parameters']['core_fraction']:.0%} of addresses removes "
        f"{100.0 * decore['boundary_transactions'] / measured['transactions']:.1f}% of the "
        f"transactions, takes the rejoinable population from {epoch['straddling_entities']} to "
        f"{decore['straddling_entities']} and the straddler subgraph's mean degree from "
        f"{epoch['mean_straddler_degree']:.2f} to {decore['mean_straddler_degree']:.2f}. It cuts by "
        "degree, and degree is where the recurring relationships live.",
        "",
        f"**`collapse` is nearly free and does not change the regime.** It costs "
        f"{100.0 * collapse['boundary_transactions'] / measured['transactions']:.1f}% of the "
        f"transactions and leaves the population and the degree where the temporal baseline leaves "
        f"them ({collapse['straddling_entities']} against {epoch['straddling_entities']} pairs, "
        f"{collapse['mean_straddler_degree']:.2f} against {epoch['mean_straddler_degree']:.2f}). "
        "It is the cut the framework asks for and it is not the binding constraint.",
        "",
        "| scheme | seed | seeds | guesses | correct | precision |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for scheme in ("epoch", "decore", "collapse"):
        for seed in rows[scheme]["seeded"]:
            precision = "n/a" if seed["precision"] is None else f"{seed['precision']:.3f}"
            lines.append(
                f"| `{scheme}` | {seed['seed_share']:.0%} | {seed['seeds']} | {seed['guesses']} | "
                f"{seed['correct']} | {precision} |"
            )
    lines += [
        "",
        "The matcher recovers a handful of pairs at best, so what separates the schemes here is the "
        "straddler subgraph and not the precision. A cut that halves the mean straddler degree "
        "leaves nothing to propagate along, whatever its precision reads on the pairs it does "
        "return.",
        "",
        "Every scheme generalises to n views:",
        "",
        "| scheme | 2 | 3 | 4 |",
        "|---|---|---|---|",
    ]
    for scheme in ("epoch", "decore", "collapse"):
        sizes = measured["view_counts"][scheme]
        cells = " | ".join("/".join(str(n) for n in sizes[str(count)]) for count in (2, 3, 4))
        lines.append(f"| `{scheme}` | {cells} |")
    lines += [
        "",
        "Cluster membership here is a co-spend label rather than wallet ownership, the export "
        "carries no output values so the collapse detector sees only its shape rule, and this is "
        "one slice of one era. None of it is a privacy score.",
        "",
    ]
    return "\n".join(lines)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("reproduce", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--artifact", required=True)
        command.add_argument("--markdown", required=True)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    if args.command == "reproduce":
        artifact = build_artifact(args.dataset)
        write_canonical_json(args.artifact, artifact)
        destination = Path(args.markdown)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_markdown(artifact), encoding="utf-8")
    else:
        artifact = verify_artifact(load_artifact(args.artifact), args.dataset)
        if Path(args.markdown).read_text(encoding="utf-8") != render_markdown(artifact):
            raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
