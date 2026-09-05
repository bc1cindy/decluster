"""Reproduce construction-fingerprint separation on a frozen transaction snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..fingerprint_validate import LibraryScorer, evaluate
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "fingerprint-validation-v1"
DEFAULT_DATASET = "tests/fixtures/fingerprint_blkcache_sample.json"


class VerificationError(ValueError):
    """The dataset or stored result violates this experiment's contract."""


def _load(path):
    try:
        with Path(path).open(encoding="utf-8") as source:
            transactions = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read transaction snapshot {path}: {exc}") from exc
    if not isinstance(transactions, list) or len(transactions) < 2:
        raise VerificationError("transaction snapshot must contain at least two transactions")
    txids = set()
    for index, transaction in enumerate(transactions):
        if not isinstance(transaction, dict) or not isinstance(transaction.get("txid"), str):
            raise VerificationError(f"transaction {index} must be an object with a string txid")
        if transaction["txid"] in txids:
            raise VerificationError(f"duplicate transaction id: {transaction['txid']}")
        txids.add(transaction["txid"])
    return transactions


def build_artifact(dataset=DEFAULT_DATASET):
    transactions = _load(dataset)
    measurement = evaluate(transactions, LibraryScorer(), cap=4000, seed=0)
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "measurement": {"transactions": len(transactions), **measurement},
        "parameters": {
            "positive_pair_draw_cap": 4000,
            "negative_pair_draw_cap": 4000,
            "seed": 0,
            "same_wallet_consistency": 0.95,
            "rarity_floor_count": 1000,
            "scorer": "canonical construction-fingerprint library",
        },
        "labels": {
            "positive": "distinct transactions sharing an input address",
            "negative": "random distinct-transaction pairs",
        },
        "limitations": [
            "address reuse is a weak same-wallet label and shares script information with the features",
            "positive pairs are draws with replacement rather than independent observations",
            "random negative pairs can include transactions controlled by the same wallet",
            "the 600-transaction snapshot is selected and is not a chain-wide sample",
            "the source recipe is unavailable; the dataset publisher authorized redistribution on 2026-09-04",
            "the result measures pair ranking and is not an ownership certificate or privacy score",
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
        raise VerificationError("unsupported fingerprint-validation artifact identity")
    measured = build_artifact(dataset)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    measured = artifact["measurement"]
    return "\n".join([
        "# Construction-fingerprint pair separation",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"Transactions: {measured['transactions']}; positive draws: {measured['n_pos']}; "
        f"negative draws: {measured['n_neg']}.",
        "",
        "| metric | value |",
        "|---|---:|",
        f"| positive mean bits | {measured['pos_mean']:.6f} |",
        f"| negative mean bits | {measured['neg_mean']:.6f} |",
        f"| AUC | {measured['auc']:.6f} |",
        f"| shuffled-label AUC | {measured['shuffle_auc']:.6f} |",
        "",
        "The canonical fingerprint scorer separates address-reuse-labelled pairs from random "
        "pairs on this selected snapshot. Address reuse is a weak and partly feature-dependent "
        "label, so this is pair-ranking evidence, not wallet attribution or a privacy score.",
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
