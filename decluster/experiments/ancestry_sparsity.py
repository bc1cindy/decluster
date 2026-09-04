"""Measure nearest-neighbour sparsity in a frozen ancestry-signature snapshot."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import statistics
from pathlib import Path

from ..def1_sparsity import survival
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "ancestry-sparsity-v1"
EPSILONS = (0.5, 0.9, 0.99)


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _load_signatures(path):
    try:
        with gzip.open(path, "rt", encoding="utf-8") as source:
            raw = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read signature snapshot {path}: {exc}") from exc
    if not isinstance(raw, dict) or len(raw) < 2:
        raise VerificationError("signature snapshot must contain at least two records")
    signatures = {}
    stored_tops = {}
    for coin, record in raw.items():
        if not isinstance(record, dict) or set(record) != {"sig", "top"}:
            raise VerificationError(f"record {coin!r} has an invalid schema")
        signature = record["sig"]
        if not isinstance(signature, dict) or not signature:
            raise VerificationError(f"record {coin!r} has no signature")
        values = {feature: float(value) for feature, value in signature.items()}
        if any(not math.isfinite(value) or value < 0 for value in values.values()):
            raise VerificationError(f"record {coin!r} has an invalid signature weight")
        signatures[str(coin)] = values
        stored_tops[str(coin)] = float(record["top"])
    return signatures, stored_tops


def _nearest_cosines(signatures):
    """Return exact nearest-neighbour cosines using a sparse inverted index."""
    coins = sorted(signatures)
    normalized = {}
    postings = {}
    for coin in coins:
        signature = signatures[coin]
        norm = math.sqrt(sum(value * value for value in signature.values()))
        vector = {feature: value / norm for feature, value in signature.items()} if norm else {}
        normalized[coin] = vector
        for feature, value in vector.items():
            postings.setdefault(feature, []).append((coin, value))

    similarities = {coin: {} for coin in coins}
    for entries in postings.values():
        for left_index, (left, left_value) in enumerate(entries):
            for right, right_value in entries[left_index + 1:]:
                contribution = left_value * right_value
                similarities[left][right] = similarities[left].get(right, 0.0) + contribution
                similarities[right][left] = similarities[right].get(left, 0.0) + contribution
    return {
        coin: max(similarities[coin].values(), default=0.0)
        for coin in coins
    }


def build_artifact(dataset):
    signatures, stored_tops = _load_signatures(dataset)
    nearest = _nearest_cosines(signatures)
    values = list(nearest.values())
    dimensions = [len(signature) for signature in signatures.values()]
    curve = survival(values, EPSILONS)
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "snapshot": {
            "records": len(signatures),
            "dimensions": {
                "minimum": min(dimensions),
                "median": statistics.median(dimensions),
                "maximum": max(dimensions),
            },
        },
        "nearest_neighbour_cosine": {
            "median": round(statistics.median(values), 15),
            "survival": {str(epsilon): curve[epsilon] for epsilon in EPSILONS},
        },
        "stored_top_context": {
            "different_from_snapshot_recomputation": sum(
                abs(nearest[coin] - stored_tops[coin]) > 1e-9 for coin in signatures
            ),
            "interpretation": "stored values were computed in an unavailable comparison population",
        },
        "limitations": [
            "the 200-record frozen snapshot is selected and is not a uniform chain sample",
            "the signature-generation recipe and original comparison population are unavailable",
            "the run measures sparsity within this snapshot only",
            "sparsity is an attack precondition, not proof of successful attribution",
            "the run does not establish a chain-wide population rate",
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


def verify_artifact(artifact, dataset):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported ancestry-sparsity artifact identity")
    measured = build_artifact(dataset)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh snapshot analysis")
    return measured


def render_markdown(artifact):
    snapshot = artifact["snapshot"]
    nearest = artifact["nearest_neighbour_cosine"]
    dimensions = snapshot["dimensions"]
    curve = nearest["survival"]
    return "\n".join([
        "# Ancestry-signature sparsity snapshot",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"The frozen snapshot contains {snapshot['records']} signatures. Their feature counts have "
        f"minimum {dimensions['minimum']}, median {dimensions['median']:.1f} and maximum "
        f"{dimensions['maximum']}.",
        "",
        f"The median recomputed nearest-neighbour cosine is {nearest['median']:.6f}. The fractions "
        f"with a neighbour above 0.5, 0.9 and 0.99 are {curve['0.5']:.3f}, "
        f"{curve['0.9']:.3f} and {curve['0.99']:.3f}.",
        "",
        f"Stored nearest-neighbour values differ from the self-contained snapshot recomputation for "
        f"{artifact['stored_top_context']['different_from_snapshot_recomputation']} records and are "
        "therefore excluded from the result.",
        "",
        "This measures an attack precondition within a selected frozen snapshot. It is neither a "
        "chain-wide estimate nor proof of successful attribution.",
        "",
    ])


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("reproduce", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--dataset", required=True)
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
        actual = Path(args.markdown).read_text(encoding="utf-8")
        if actual != render_markdown(artifact):
            raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
