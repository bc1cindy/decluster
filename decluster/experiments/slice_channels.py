"""Reproduce stable attribute-density and graph-shape observations on a frozen slice.

The snapshot is an address-only export: it carries no version, locktime, sequence or fee, so all
four contraction axes abstain on every transaction and the vertex feature vectors are structural
alone. The run reports the per-axis skip counts rather than leaving that to be inferred, because an
earlier revision read the missing fields as values — every vertex then agreed on `version` and
`locktime` for free, and the similarity those constants added is what the density figures carried.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from .. import contraction, def1_sparsity, graph_shape, views
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "slice-channels-v1"
DEFAULT_DATASET = "tests/fixtures/slice_a_channels_2016.ndjson.gz"


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


def _density(graph, min_degree, epsilons):
    tops = def1_sparsity.nearest_similarities(
        graph,
        query_n=1200,
        background_n=12000,
        min_degree=min_degree,
        seed=0,
    )
    return {
        "eligible_sample": len(tops),
        "survival": {str(epsilon): value for epsilon, value in
                     def1_sparsity.survival(tops, epsilons=epsilons).items()},
    }


def build_artifact(dataset=DEFAULT_DATASET):
    sample = _load(dataset)
    lookup = views.cluster_addresses(sample, refuse=True)
    graph = contraction.contract(sample, lookup=lookup, axes=True)
    shape = graph_shape.summary(graph)
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "measurement": {
            "transactions": len(sample),
            "clustered_addresses": len(lookup),
            "clusters": len(set(lookup.values())),
            "axis_values_recorded": {axis: sum(counts.values())
                                     for axis, counts in sorted(graph.base_rates.items())},
            "axis_transactions_skipped": {axis: graph.skipped.get(axis, 0)
                                          for axis in sorted(graph.base_rates)},
            "density_min_degree_2": _density(graph, 2, (0.5, 0.9, 0.99)),
            "density_min_degree_20": _density(graph, 20, (0.9,)),
            "graph_shape": shape,
        },
        "parameters": {
            "refuse_guard": True,
            "query_records": 1200,
            "background_records": 12000,
            "seed": 0,
            "similarity": "cosine over normalized feature vectors",
        },
        "limitations": [
            "the snapshot carries none of the four axes, so the similarity measured here is structural",
            "the snapshot contains six 2016 blocks and is not a chain-wide sample",
            "the run does not reproduce historical measurements on larger unpreserved slices",
            "dense attributes do not prove resistance to other linkage channels",
            "negative assortativity does not by itself determine graph-matching performance",
            "the snapshot recipe is unavailable; the dataset publisher authorized redistribution on 2026-09-04",
            "the result is not a privacy score or CoinScore",
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
        raise VerificationError("unsupported slice-channel artifact identity")
    measured = build_artifact(dataset)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    measured = artifact["measurement"]
    ordinary = measured["density_min_degree_2"]
    hubs = measured["density_min_degree_20"]
    shape = measured["graph_shape"]
    return "\n".join([
        "# Attribute density and graph shape on a six-block slice",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"Transactions: {measured['transactions']}; clusters: {measured['clusters']}; "
        f"contracted vertices: {shape['vertices']}.",
        "",
        "| minimum degree | sampled records | delta(0.5) | delta(0.9) | delta(0.99) |",
        "|---:|---:|---:|---:|---:|",
        f"| 2 | {ordinary['eligible_sample']} | {ordinary['survival']['0.5']:.6f} | "
        f"{ordinary['survival']['0.9']:.6f} | {ordinary['survival']['0.99']:.6f} |",
        f"| 20 | {hubs['eligible_sample']} | n/a | {hubs['survival']['0.9']:.6f} | n/a |",
        "",
        f"Degree assortativity: {shape['assortativity']:.6f}.",
        "",
        f"This export carries none of the four axes — every one of the {measured['transactions']} "
        "transactions abstains on version, input order, locktime and fee rate — so the vectors "
        "compared here are structural: degree, transaction count, self-transfers and the "
        "neighbour-degree histogram. On those alone the space is dense, and markedly less so among "
        f"the higher-degree vertices ({hubs['survival']['0.9']:.3f} against "
        f"{ordinary['survival']['0.9']:.3f} at the same threshold), which is where a matcher would "
        "start. The contracted graph is disassortative. These observations do not reproduce the "
        "historical larger slices, do not measure attribute density, and do not establish "
        "graph-matching performance.",
        "",
    ])


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    commands = parser.add_subparsers(dest="command", required=True)
    reproduce = commands.add_parser("reproduce")
    reproduce.add_argument("--artifact", required=True)
    reproduce.add_argument("--markdown", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--artifact", required=True)
    verify.add_argument("--markdown")
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
        if args.markdown is not None:
            actual = Path(args.markdown).read_text(encoding="utf-8")
            if actual != render_markdown(artifact):
                raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
