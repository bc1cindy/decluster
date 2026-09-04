"""Ablate two excluded fingerprint axes on a frozen transaction snapshot."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from ..fingerprint_validate import LibraryScorer, reuse_pairs
from ..graph_deanon import auc, shuffle_auc
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "fingerprint-catalog-axes-v1"
DEFAULT_DATASET = "tests/fixtures/fingerprint_blkcache_sample.json"
PAIR_CAP = 4000
SEED = 0


class VerificationError(ValueError):
    """The dataset or stored result violates this experiment's contract."""


def _output_count(transaction):
    count = len(transaction["vout"])
    if count == 1:
        return "1"
    if count == 2:
        return "2"
    if count == 3:
        return "3"
    return "4plus"


def _segwit_serialization(transaction):
    return "segwit" if any(entry.get("witness") for entry in transaction["vin"]) else "non_segwit"


DIAGNOSTIC_AXES = {
    "output_count": _output_count,
    "segwit_serialization": _segwit_serialization,
}


def _load(path):
    try:
        with Path(path).open(encoding="utf-8") as source:
            transactions = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read transaction snapshot {path}: {exc}") from exc
    if not isinstance(transactions, list) or len(transactions) < 2:
        raise VerificationError("transaction snapshot must contain at least two transactions")
    identifiers = []
    for index, transaction in enumerate(transactions):
        if not isinstance(transaction, dict) or not isinstance(transaction.get("txid"), str):
            raise VerificationError(f"transaction {index} must have a string txid")
        if not isinstance(transaction.get("vin"), list) or not isinstance(transaction.get("vout"), list):
            raise VerificationError(f"transaction {index} must have input and output arrays")
        identifiers.append(transaction["txid"])
    if len(identifiers) != len(set(identifiers)):
        raise VerificationError("transaction ids must be unique")
    return transactions


def _probabilities(transactions, extractor):
    counts = Counter(extractor(transaction) for transaction in transactions)
    return {value: count / len(transactions) for value, count in sorted(counts.items())}


def _scorer(transactions, axes):
    scorer = LibraryScorer()
    for name in axes:
        extractor = DIAGNOSTIC_AXES[name]
        probabilities = _probabilities(transactions, extractor)
        collision = sum(probability * probability for probability in probabilities.values())
        scorer.axes.append((
            name,
            extractor,
            probabilities,
            collision,
            lambda left, right, known=probabilities: left not in known and right not in known,
        ))
    return scorer


def _measure(scorer, positive_pairs, negative_pairs):
    positive = [scorer.score(left, right) for left, right in positive_pairs]
    negative = [scorer.score(left, right) for left, right in negative_pairs]
    return {
        "positive_mean": sum(positive) / len(positive),
        "negative_mean": sum(negative) / len(negative),
        "auc": auc(positive, negative, SEED),
        "shuffled_auc": shuffle_auc(positive, negative, SEED),
    }


def build_artifact(dataset=DEFAULT_DATASET):
    transactions = _load(dataset)
    positive_pairs, negative_pairs = reuse_pairs(transactions, PAIR_CAP, SEED)
    configurations = (
        ("library", ()),
        ("plus_output_count", ("output_count",)),
        ("plus_segwit_serialization", ("segwit_serialization",)),
        ("plus_both", ("output_count", "segwit_serialization")),
    )
    rows = []
    base_auc = None
    for label, axes in configurations:
        measurement = _measure(_scorer(transactions, axes), positive_pairs, negative_pairs)
        if base_auc is None:
            base_auc = measurement["auc"]
        rows.append({
            "configuration": label,
            "added_axes": list(axes),
            **measurement,
            "auc_delta_from_library": measurement["auc"] - base_auc,
        })
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "measurement": {
            "transactions": len(transactions),
            "positive_pair_draws": len(positive_pairs),
            "negative_pair_draws": len(negative_pairs),
            "rows": rows,
        },
        "diagnostic_axis_probabilities": {
            name: _probabilities(transactions, extractor)
            for name, extractor in DIAGNOSTIC_AXES.items()
        },
        "parameters": {
            "pair_draw_cap": PAIR_CAP,
            "seed": SEED,
            "probability_source": "same frozen snapshot",
            "same_wallet_consistency": 0.95,
            "rarity_floor_count": 1000,
        },
        "limitations": [
            "address reuse is a weak and partly feature-dependent same-wallet proxy",
            "diagnostic probabilities are fitted and evaluated on the same selected snapshot",
            "the 600-transaction snapshot is not either historical 166k or 180k cache",
            "AUC deltas on one snapshot do not establish conditional dependence",
            "the axes remain excluded from the production fingerprint library",
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
        raise VerificationError("unsupported fingerprint-catalog-axes artifact identity")
    measured = build_artifact(dataset)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh axis-ablation execution")
    return measured


def render_markdown(artifact):
    measurement = artifact["measurement"]
    lines = [
        "# Excluded fingerprint-axis ablation",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"Transactions: {measurement['transactions']}; positive draws: "
        f"{measurement['positive_pair_draws']}; negative draws: "
        f"{measurement['negative_pair_draws']}.",
        "",
        "| configuration | AUC | delta from library | shuffled AUC |",
        "|---|---:|---:|---:|",
    ]
    for row in measurement["rows"]:
        lines.append(
            f"| {row['configuration']} | {row['auc']:.6f} | "
            f"{row['auc_delta_from_library']:+.6f} | {row['shuffled_auc']:.6f} |"
        )
    lines.extend([
        "",
        "On this frozen snapshot, output count reduces AUC, SegWit serialization increases it, "
        "and adding both yields less than SegWit serialization alone. This is consistent with "
        "the historical redundancy concern, but one selected snapshot does not prove conditional "
        "dependence. Neither diagnostic axis is added to the production library.",
        "",
    ])
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
