"""Reproduce the reduced third-round conservation observation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..conservation import forced_in_round, forced_prefixes, forced_value, slack_to_force_one_more
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "conservation-round-three-v1"
DATASET = "tests/fixtures/conservation_round_three.json"


class VerificationError(ValueError):
    """A fixture or stored result violates this experiment's contract."""


def load_fixture(path=DATASET):
    try:
        with Path(path).open(encoding="utf-8") as source:
            value = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read conservation fixture {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise VerificationError("unsupported conservation fixture identity")
    if not isinstance(value.get("txid"), str) or len(value["txid"]) != 64:
        raise VerificationError("fixture txid must be a 64-character string")
    for field in ("total_input", "known_participant_input"):
        if not isinstance(value.get(field), int) or value[field] <= 0:
            raise VerificationError(f"fixture {field} must be a positive integer")
    outputs = value.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise VerificationError("fixture outputs must be a non-empty list")
    if any(
        not isinstance(row, list)
        or len(row) != 2
        or not all(isinstance(item, int) and item > 0 for item in row)
        for row in outputs
    ):
        raise VerificationError("each output row must contain positive integer value and count")
    if len({row[0] for row in outputs}) != len(outputs):
        raise VerificationError("fixture output values must be unique")
    return value


def _transaction(fixture):
    return {
        "vin": [{"prevout": {"value": fixture["total_input"]}}],
        "vout": [
            {"value": value}
            for value, count in fixture["outputs"]
            for _ in range(count)
        ],
    }


def build_artifact(dataset=DATASET):
    fixture = load_fixture(dataset)
    transaction = _transaction(fixture)
    known_input = fixture["known_participant_input"]
    forced = forced_in_round(transaction, known_input)
    prefixes = forced_prefixes(transaction, known_input)
    if not forced:
        raise VerificationError("fixture does not produce a conservation observation")
    value, count, present = forced[0]
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "fixture": {
            "txid": fixture["txid"],
            "inputs": 454,
            "outputs": len(transaction["vout"]),
            "total_input": fixture["total_input"],
            "known_participant_input": known_input,
        },
        "largest_forced_denomination": {
            "value": value,
            "forced": count,
            "present": present,
            "forced_value": forced_value(transaction, known_input),
            "margin": slack_to_force_one_more(
                fixture["total_input"], known_input, value, present
            ),
        },
        "prefix_curve": [
            {"values": values, "forced_value": amount, "minimum_coins": coins, "pool": pool}
            for values, amount, coins, pool in prefixes
        ],
        "interpretation": "forced provenance of value under conservation",
        "limitations": [
            "the fixture is a reduced representation of one mainnet transaction",
            "the run does not reproduce the surrounding six-round chain",
            "the known participant input is supplied by an external forward walk",
            "conservation establishes provenance of value, not output ownership",
            "net settlement invalidates an ownership inference from this bound",
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


def verify_artifact(artifact, *, dataset=DATASET):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported conservation artifact identity")
    measured = build_artifact(dataset)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    fixture = artifact["fixture"]
    forced = artifact["largest_forced_denomination"]
    return "\n".join([
        "# Conservation observation for round three",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"The reduced mainnet fixture `{fixture['txid']}` contains "
        f"{fixture['outputs']} outputs. Conservation forces {forced['forced']} of the "
        f"{forced['present']} outputs worth {forced['value']} sat onto value supplied by "
        "the known participant.",
        "",
        f"The forced value is {forced['forced_value']} sat and the margin to the next "
        f"boundary is {forced['margin']} sat.",
        "",
        "This is provenance of value under conservation, not output ownership, identity "
        "attribution, a population estimate or CoinScore.",
        "",
    ])


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DATASET)
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
        artifact = verify_artifact(load_artifact(args.artifact), dataset=args.dataset)
        if args.markdown is not None:
            actual = Path(args.markdown).read_text(encoding="utf-8")
            if actual != render_markdown(artifact):
                raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
