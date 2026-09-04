"""Reproduce ancestry-signature record linkage on a frozen Bitcoin-derived snapshot."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from ..reid import stratified_reid
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "reid-v1"
DEFAULT_DATASET = "tests/fixtures/reid_sigs.json.gz"


class VerificationError(ValueError):
    """The dataset or stored result violates this experiment's contract."""


def _load(path):
    try:
        with gzip.open(path, "rt", encoding="utf-8") as source:
            value = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read signature snapshot {path}: {exc}") from exc
    if not isinstance(value, dict) or len(value) < 2:
        raise VerificationError("signature snapshot must contain at least two records")
    signatures = {}
    for coin, record in value.items():
        if not isinstance(coin, str) or not isinstance(record, dict):
            raise VerificationError("each record must have a string identifier and object value")
        signature = record.get("sig")
        if not isinstance(signature, dict) or not signature:
            raise VerificationError(f"record {coin!r} has no non-empty signature")
        parsed = {}
        for origin, weight in signature.items():
            if not isinstance(origin, str) or not isinstance(weight, (int, float)) or weight < 0:
                raise VerificationError(f"record {coin!r} has an invalid signature entry")
            parsed[origin] = float(weight)
        signatures[coin] = parsed
    return sorted(signatures), signatures


def build_artifact(dataset=DEFAULT_DATASET):
    coins, signatures = _load(dataset)
    measured = stratified_reid(coins, signatures, ms=(4, 8), phi=1.5, seed=0)
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "method": {
            "description": "ancestry-signature record-linkage adaptation",
            "auxiliary_origins": [4, 8],
            "eccentricity_threshold": 1.5,
            "seed": 0,
            "sparse_below_cosine": 0.5,
            "dense_at_least_cosine": 0.9,
        },
        "measurement": measured,
        "limitations": [
            "the 200-record snapshot is selected and is not a uniform chain sample",
            "the signature-generation recipe and original comparison population are unavailable",
            "the target identifier is a record identity, not wallet ownership ground truth",
            "the auxiliary origins are sampled from the target signature rather than observed independently",
            "this is an adaptation, not a reproduction of the published Netflix experiment",
            "the result does not establish a chain-wide deanonymization rate or privacy score",
            "dataset licensing and redistribution remain unknown in the catalog",
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
        raise VerificationError("unsupported reidentification artifact identity")
    measured = build_artifact(dataset)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    measurement = artifact["measurement"]
    lines = [
        "# Ancestry-signature record linkage",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"Snapshot records: {measurement['n']} ({measurement['n_sparse']} sparse, "
        f"{measurement['n_dense']} dense).",
        "",
        "| stratum | auxiliary origins | attackable | declared | exact | precision | exact rate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in measurement["rows"]:
        lines.append(
            f"| {row['stratum']} | {row['m']} | {row['attackable']} | {row['declared']} | "
            f"{row['exact']} | {row['precision']:.6f} | {row['exact_rate']:.6f} |"
        )
    lines.extend([
        "",
        "The selected snapshot exhibits a large sparse-versus-dense difference under this "
        "adapted attack. The auxiliary origins come from each target's own stored signature, "
        "so this demonstrates mechanism behavior under supplied auxiliary information, not "
        "independent real-world attribution or a chain-wide rate.",
        "",
    ])
    return "\n".join(lines)


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
