"""Reproduce the paired entity-labelled graph-structure observations."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from ..entities import detect_bitmex, detect_satoshidice
from ..graph_deanon import evaluate_entity
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "entity-deanon-v1"
SATOSHIDICE_DATASET = "tests/fixtures/entity_satoshidice_2013.ndjson.gz"
BITMEX_DATASET = "tests/fixtures/entity_bitmex_2019.ndjson.gz"


class VerificationError(ValueError):
    """A dataset or stored result violates this experiment's contract."""


def _load_sample(path):
    sample = []
    try:
        with gzip.open(path, "rt", encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise VerificationError(f"{path}:{line_number}: transaction must be an object")
                sample.append((value, 0))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read entity snapshot {path}: {exc}") from exc
    if not sample:
        raise VerificationError(f"entity snapshot is empty: {path}")
    return sample


def _measurement(path, labeler):
    sample = _load_sample(path)
    measured = evaluate_entity(sample, labeler, seed=0)
    return {
        "transactions": len(sample),
        "entity_clusters": measured["entity_clusters"],
        "positive_pairs": measured["pos_pairs"],
        "payment_auc": measured["auc_payment"],
        "positive_mean_shared_neighbours": measured["pos_mean"],
    }


def build_artifact(
    satoshidice_dataset=SATOSHIDICE_DATASET,
    bitmex_dataset=BITMEX_DATASET,
):
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "adversary": "payment-graph common-neighbour scorer with independent entity detector",
        "satoshidice": _measurement(satoshidice_dataset, detect_satoshidice),
        "bitmex": _measurement(bitmex_dataset, detect_bitmex),
        "interpretation": {
            "satoshidice": "positive control with recurring counterparties",
            "bitmex": "null control with hub-and-spoke deposit structure",
        },
        "limitations": [
            "the fixtures are selected entity-centred subgraphs, not uniform chain samples",
            "vanity-prefix detectors label the fixtures and are not general entity attribution",
            "the run evaluates common-neighbour structure, not the full Narayanan-Shmatikov algorithm",
            "the contrast does not establish a universal property of gambling services or exchanges",
            "upstream data licensing is undetermined; the dataset publisher authorized redistribution on 2026-09-04",
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


def verify_artifact(artifact, **datasets):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported entity-deanon artifact identity")
    measured = build_artifact(**datasets)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    dice = artifact["satoshidice"]
    bitmex = artifact["bitmex"]
    return "\n".join([
        "# Entity-labelled graph-structure observations",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "| snapshot | transactions | positive pairs | payment AUC | mean shared neighbours |",
        "|---|---:|---:|---:|---:|",
        f"| SatoshiDice | {dice['transactions']} | {dice['positive_pairs']} | "
        f"{dice['payment_auc']:.6f} | {dice['positive_mean_shared_neighbours']:.6f} |",
        f"| BitMEX | {bitmex['transactions']} | {bitmex['positive_pairs']} | "
        f"{bitmex['payment_auc']:.6f} | {bitmex['positive_mean_shared_neighbours']:.6f} |",
        "",
        "The selected SatoshiDice subgraph is a positive control and the selected BitMEX "
        "subgraph is a null control. This contrast is snapshot-specific and is not general "
        "entity attribution or the full Narayanan–Shmatikov attack.",
        "",
    ])


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--satoshidice-dataset", default=SATOSHIDICE_DATASET)
    parser.add_argument("--bitmex-dataset", default=BITMEX_DATASET)
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
    datasets = {
        "satoshidice_dataset": args.satoshidice_dataset,
        "bitmex_dataset": args.bitmex_dataset,
    }
    if args.command == "reproduce":
        artifact = build_artifact(**datasets)
        write_canonical_json(args.artifact, artifact)
        destination = Path(args.markdown)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_markdown(artifact), encoding="utf-8")
    else:
        artifact = verify_artifact(load_artifact(args.artifact), **datasets)
        if args.markdown is not None:
            actual = Path(args.markdown).read_text(encoding="utf-8")
            if actual != render_markdown(artifact):
                raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
