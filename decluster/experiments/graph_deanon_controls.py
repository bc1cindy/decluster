"""Publish the graph-structure AUC together with the control that qualifies it.

`PAPER.md` cites AUC 0.95 for payment-graph structure predicting same-cluster membership, and the
fixture it comes from was in the dataset catalogue but owned by no run. Publishing the headline
without its control would be the easier half: `_pairs` samples negatives without matching degree,
and a same-cluster pair is systematically higher-degree than a random one, so part of any AUC
measured that way is the sampling rather than shared structure.

So the run reports both, plus the degree-only score — a number that is the pair's degree sum and
nothing else. Under degree-matched negatives that score is at chance by construction, which is what
makes it a usable ruler for how much of the headline the asymmetry was carrying.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from .. import graph_deanon
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "graph-deanon-controls-v1"
DEFAULT_DATASET = "tests/fixtures/graph_deanon_2016.ndjson.gz"
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
        raise VerificationError(f"cannot read graph fixture {path}: {exc}") from exc
    if not sample:
        raise VerificationError(f"graph fixture is empty: {path}")
    return sample


def build_artifact(dataset=DEFAULT_DATASET):
    sample = _load(dataset)
    published = graph_deanon.evaluate(sample, seed=SEED)
    matched = graph_deanon.degree_matched_auc(sample, seed=SEED)
    views = {}
    for view in ("full", "payment"):
        views[view] = {
            "published_auc": published[f"auc_{view}"],
            "degree_matched_auc": matched[f"auc_{view}"],
            "degree_only_auc_under_matching": matched[f"degree_only_{view}"],
            "fall_under_matching": published[f"auc_{view}"] - matched[f"auc_{view}"],
            "positive_pairs": matched[f"pos_pairs_{view}"],
            "matched_negative_pairs": matched[f"neg_pairs_{view}"],
        }
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "dataset": "graph-deanon-2016-v1",
        "measurement": {
            "transactions": len(sample),
            "addresses": published["addrs"],
            "clusters_with_two_or_more": published["clusters_ge2"],
            "published_negative_pairs": published["neg_pairs"],
            "shuffled_label_auc": published["auc_shuffle"],
            "views": views,
        },
        "parameters": {
            "seed": SEED,
            "negative_sampling_published": "uniform over non-co-spent pairs, capped",
            "negative_sampling_control": "degree-matched to each positive",
            "score": "rarity-weighted shared-neighbour structure",
        },
        "limitations": [
            "cluster membership is a co-spend label, not wallet ownership",
            "one selected 2016 fixture, not a chain-wide sample",
            "the degree-matched control changes the negative population, not the positives",
            "a fall under matching bounds how much of the AUC was degree asymmetry; it does not "
            "establish what the remainder is",
            "neither number is a re-identification rate or a privacy score",
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
        raise VerificationError("unsupported graph-deanon-control artifact identity")
    measured = build_artifact(dataset)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    measured = artifact["measurement"]
    lines = [
        "# Graph-structure linkage and the degree-matched control",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"{measured['transactions']} transactions, {measured['addresses']} addresses, "
        f"{measured['clusters_with_two_or_more']} clusters of two or more. Positives are "
        "same-cluster pairs that do not co-spend; the score is rarity-weighted shared-neighbour "
        "structure.",
        "",
        "| view | published AUC | degree-matched AUC | fall | degree-only AUC under matching |",
        "|---|---:|---:|---:|---:|",
    ]
    for view, row in sorted(measured["views"].items()):
        lines.append(
            f"| {view} | {row['published_auc']:.4f} | {row['degree_matched_auc']:.4f} | "
            f"{row['fall_under_matching']:.4f} | {row['degree_only_auc_under_matching']:.4f} |"
        )
    payment = measured["views"]["payment"]
    lines += [
        "",
        f"The payment-graph headline falls {payment['fall_under_matching']:.4f} under degree-matched "
        f"negatives, from {payment['published_auc']:.4f} to {payment['degree_matched_auc']:.4f}. "
        "Under that control a score made only of the pair's degree sum reads "
        f"{payment['degree_only_auc_under_matching']:.4f} — chance, by construction — so the "
        "remaining separation is not the asymmetry the published sampling leaves in.",
        "",
        f"The shuffled-label control reads {measured['shuffled_label_auc']:.4f}, which is what says "
        "the score is measuring the labels at all.",
        "",
        "Cluster membership here is a co-spend label rather than wallet ownership, the fixture is "
        "one selected 2016 slice, and a fall under matching bounds how much of the AUC was degree "
        "asymmetry without establishing what the remainder is. Neither number is a "
        "re-identification rate or a privacy score.",
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
