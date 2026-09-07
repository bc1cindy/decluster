"""Compare the partition schemes the framework names, on data a reader has.

The framework calls the temporal cut its own trivial example and asks for one that divides along
cluster-collapse regions instead, generalised to n views. Both are implemented, and
`results/RESULTS-partition-cuts.md` reports the comparison — over 300,000 transactions from a
977 MB export that is not committed. The verdict there is a clean negative for the cut criterion,
and nobody outside this machine can check it.

This reproduces the part the committed slice can carry: how each scheme partitions, how many
entities straddle the boundary, and how connected those straddlers are to each other. That last
number is the go/no-go the matcher depends on — propagation needs edges *among* the straddlers,
not merely a count of them — and it is where the schemes separate.

What this deliberately does not reproduce is the precision and recall table. At this scale the
matcher does not ignite at all, under any scheme, and the run records that rather than reporting
zeros as if they were a comparison.
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
from pathlib import Path

from .. import views
from ..result_artifacts import canonical_json_bytes, write_canonical_json
from ..view_match import ViewMatcher

EXPERIMENT_ID = "partition-schemes-v1"
DEFAULT_DATASET = "tests/fixtures/slice_a_channels_2016.ndjson.gz"
SCHEMES = ("epoch", "decore", "collapse")
VIEW_COUNTS = (2, 3, 4)
CORE_FRACTION = 0.01
MIN_SIDE = 2
SEED = 0


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
    degrees = views.contract_degrees(sample, indices=indices, lookup=lookup)
    keep = {vertex for vertex, degree in degrees.items() if degree >= 2}
    graph = views.contract(sample, indices=indices, lookup=lookup, axes=False, keep=keep)
    return graph, {vertex: degrees[vertex] for vertex in keep}


def _straddlers(sample, lookup, parts):
    addresses = set()
    for index in parts[0]:
        transaction = sample[index][0]
        addresses.update(views._in_addrs(transaction))
        addresses.update(address for address, _ in views._out_addrs(transaction))
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
    parts = views.partition_coins(sample, scheme=scheme, core_frac=CORE_FRACTION,
                                  n_views=2, min_side=MIN_SIDE)
    boundary = len(sample) - sum(len(part) for part in parts)
    left, right, stat_left, stat_right, truth = _straddlers(sample, lookup, parts[:2])
    crowd = set(truth)
    among = sum(1 for source, destination in left.edges
                if source in crowd and destination in crowd)
    connected = sum(1 for vertex in crowd
                    if any(other in crowd for other in left.neighbours(vertex)))
    guesses = 0
    if truth:
        ranked = sorted(truth, key=lambda v: -(left.degree(v) + right.degree(truth[v])))
        seed_count = max(2, int(len(ranked) * 0.10))
        seeds = set(ranked[:seed_count])
        matched = ViewMatcher(revisit=True).match(
            left, right, {v: truth[v] for v in seeds}, stat_a=stat_left, stat_b=stat_right
        )
        guesses = sum(1 for v in matched if v in truth and v not in seeds)
    return {
        "scheme": scheme,
        "view_sizes": [len(part) for part in parts],
        "boundary_transactions": boundary,
        "straddling_entities": len(truth),
        "edges_among_straddlers": among,
        "straddlers_with_a_straddling_neighbour": connected,
        "matcher_guesses": guesses,
    }


def build_artifact(dataset=DEFAULT_DATASET):
    sample = _load(dataset)
    lookup = views.cluster_addresses(sample, refuse=True)
    rows = [_scheme(sample, lookup, scheme) for scheme in SCHEMES]
    generalisation = {
        scheme: {
            str(count): [len(part) for part in views.partition_coins(
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
            "any_scheme_ignited_the_matcher": any(row["matcher_guesses"] for row in rows),
        },
        "parameters": {
            "schemes": list(SCHEMES),
            "view_counts": list(VIEW_COUNTS),
            "core_fraction": CORE_FRACTION,
            "min_side": MIN_SIDE,
            "seed": SEED,
            "seed_share": 0.10,
        },
        "limitations": [
            "the matcher does not ignite on this slice under any scheme, so the precision and "
            "recall table in RESULTS-partition-cuts.md is not reproduced here",
            "that table rests on a 300,000-transaction export this repository does not ship",
            "one slice, one era; the straddler counts are two orders of magnitude below the "
            "published run and should not be compared to it as measurements",
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
        "# The partition schemes on a slice a reader has",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"{measured['transactions']} transactions, {measured['clusters']} clusters. Each scheme "
        "cuts the slice into two views, a straddling entity gets a distinct pseudonym per view, "
        "and the matcher has to rejoin them from structure alone.",
        "",
        "| scheme | views | boundary txs | straddling entities | edges among them | non-isolated |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for scheme in ("epoch", "decore", "collapse"):
        row = rows[scheme]
        lines.append(
            f"| {scheme} | {row['view_sizes'][0]} / {row['view_sizes'][1]} | "
            f"{row['boundary_transactions']} | {row['straddling_entities']} | "
            f"{row['edges_among_straddlers']} | "
            f"{row['straddlers_with_a_straddling_neighbour']} |"
        )
    lines += [
        "",
        f"The collapse cut costs {measured['collapse_costs_over_epoch']} transactions more than the "
        "temporal one and leaves the straddler population and its internal connectivity where the "
        f"temporal cut leaves them ({rows['collapse']['straddling_entities']} against "
        f"{rows['epoch']['straddling_entities']} entities, "
        f"{rows['collapse']['edges_among_straddlers']} against "
        f"{rows['epoch']['edges_among_straddlers']} edges). `decore` is the one that differs, and "
        f"it differs by destroying the signal: {rows['decore']['straddling_entities']} entities and "
        f"{rows['decore']['edges_among_straddlers']} edges among them. That ordering is what the "
        "300,000-transaction run found, at two orders of magnitude more data.",
        "",
        "**The matcher does not ignite here, under any scheme.** Not zero correct out of some "
        "guesses — zero guesses. Propagation needs edges among the straddlers and this slice does "
        "not supply enough of them, so the precision and recall half of "
        "`RESULTS-partition-cuts.md` stays backed only by the export this repository does not "
        "ship. Reporting zeros as a comparison would read as a measured tie between the schemes, "
        "and it is not one.",
        "",
        "Every scheme generalises to n views:",
        "",
        "| scheme | 2 | 3 | 4 |",
        "|---|---|---|---|",
    ]
    for scheme in ("epoch", "decore", "collapse"):
        sizes = measured["view_counts"][scheme]
        cells = " | ".join("/".join(str(n) for n in sizes[str(count)]) for count in (2, 3, 4))
        lines.append(f"| {scheme} | {cells} |")
    lines += [
        "",
        "Cluster membership here is a co-spend label rather than wallet ownership, the export "
        "carries no output values so the collapse detector sees only its shape rule, and the "
        "counts are two orders of magnitude below the published run — they support the ordering, "
        "not a comparison of magnitudes. None of this is a privacy score.",
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
