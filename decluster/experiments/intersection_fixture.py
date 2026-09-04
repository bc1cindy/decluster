"""Reproduce a synthetic cluster-level provenance intersection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from examples.intersection_pipeline import run

from ..adaptations.ancestry import ancestry_signature_report
from ..result_artifacts import canonical_json_bytes, write_canonical_json


EXPERIMENT_ID = "intersection-cluster-fixture-v1"


class VerificationError(ValueError):
    """A stored fixture result differs from a fresh execution."""


def _fixture():
    transactions = {
        "origin": {
            "vin": [{"is_coinbase": True}],
            "vout": [{"value": 5}, {"value": 5}],
        },
        "left-source": {
            "vin": [{"is_coinbase": True}],
            "vout": [{"value": 5}],
        },
        "right-source": {
            "vin": [{"is_coinbase": True}],
            "vout": [{"value": 5}],
        },
        "left": {
            "vin": [
                {"txid": "origin", "vout": 0, "prevout": {"value": 5}},
                {"txid": "left-source", "vout": 0, "prevout": {"value": 5}},
            ],
            "vout": [{"value": 10}],
        },
        "right": {
            "vin": [
                {"txid": "origin", "vout": 1, "prevout": {"value": 5}},
                {"txid": "right-source", "vout": 0, "prevout": {"value": 5}},
            ],
            "vout": [{"value": 10}],
        },
        "join": {
            "vin": [
                {"txid": "left", "vout": 0, "prevout": {"value": 10}},
                {"txid": "right", "vout": 0, "prevout": {"value": 10}},
            ],
            "vout": [{"value": 20}],
        },
    }
    outspends = {
        "left": [{"spent": True, "txid": "join"}],
        "right": [{"spent": True, "txid": "join"}],
        "join": [{"spent": False}],
    }
    return transactions, outspends


def build_artifact():
    transactions, outspends = _fixture()
    fetch = transactions.__getitem__
    result = run(
        seeds=[("left", 0), ("right", 0)],
        get_tx=fetch,
        get_outspends=lambda txid: outspends.get(txid, []),
        ancestry_report_of=lambda outpoint: ancestry_signature_report(
            outpoint, depth=2, fetch=fetch
        ),
        intersection_options={"cluster_of": lambda coin: coin[0]},
        max_depth=1,
    )
    narrowing = result["results"][0]["narrowing"]
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "parameters": {
            "ancestry_depth": 2,
            "cluster_key": "creating transaction id",
            "monitor_depth": 1,
        },
        "fixture": {
            "seeds": [["left", 0], ["right", 0]],
            "transactions": transactions,
        },
        "result": result,
        "summary": {
            "blind": narrowing["blind"],
            "branches": narrowing["branches"],
            "candidates_before": min(narrowing["sizes"]),
            "candidates_after": len(narrowing["shared"]),
            "collapsed": narrowing["collapsed"],
            "scored": narrowing["scored"],
        },
        "limitations": [
            "synthetic fixture",
            "narrowing is conditional on the observed co-spend",
            "the fixture does not run the clustering verdict",
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


def verify_artifact(artifact):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported intersection artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh fixture execution")
    return measured


def render_markdown(artifact):
    summary = artifact["summary"]
    return "\n".join([
        "# Cluster-level provenance intersection fixture",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "| quantity | value |",
        "|---|---:|",
        f"| branches | {summary['branches']} |",
        f"| candidates before | {summary['candidates_before']} |",
        f"| candidates after | {summary['candidates_after']} |",
        f"| candidates removed | {summary['collapsed']} |",
        f"| blind | `{str(summary['blind']).lower()}` |",
        f"| independently scored | `{str(summary['scored']).lower()}` |",
        "",
        "This is a synthetic, conditional narrowing. It is not an ownership attribution.",
        "",
    ])


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
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
        artifact = build_artifact()
        write_canonical_json(args.artifact, artifact)
        destination = Path(args.markdown)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_markdown(artifact), encoding="utf-8")
    else:
        artifact = verify_artifact(load_artifact(args.artifact))
        if args.markdown is not None:
            actual = Path(args.markdown).read_text(encoding="utf-8")
            if actual != render_markdown(artifact):
                raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
