"""Reproduce the attributed pseudonym-graph contraction contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..adaptations.pseudonym_graph import contract_report
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "pseudonym-graph-contract-v1"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _transaction(identifier, source, outputs, height):
    return {
        "txid": identifier,
        "height": height,
        "version": 2,
        "locktime": 0,
        "fee": 100,
        "weight": 400,
        "vin": [{
            "txid": f"previous-{source}",
            "vout": 0,
            "sequence": 0xFFFFFFFF,
            "prevout": {
                "value": 10_000,
                "scriptpubkey_type": "v0_p2wpkh",
                "scriptpubkey_address": source,
            },
        }],
        "vout": [
            {
                "value": value,
                "scriptpubkey_type": "v0_p2wpkh",
                "scriptpubkey_address": destination,
            }
            for destination, value in outputs
        ],
    }


def fixture():
    transactions = (
        _transaction("forward-1", "a", (("x", 100), ("y", 200)), 100),
        _transaction("forward-2", "b", (("x", 300),), 140),
        _transaction("reverse", "x", (("a", 50),), 120),
        _transaction("self", "a", (("b", 25),), 130),
        _transaction("singleton", "z", (("a", 10),), 150),
    )
    return tuple((transaction, None) for transaction in transactions), {
        "a": "cluster-a",
        "b": "cluster-a",
        "x": "cluster-x",
        "y": "cluster-x",
    }


def build_artifact():
    sample, lookup = fixture()
    report = contract_report(sample, lookup)
    evidence = report.channels[0].evidence[0]
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "vertices": [vertex.identifier for vertex in evidence.vertices],
        "edges": [
            {
                "source": edge.source.identifier,
                "target": edge.target.identifier,
                "transfers": edge.transfers,
                "value": edge.value,
                "first_height": edge.first_height,
                "last_height": edge.last_height,
            }
            for edge in evidence.edges
        ],
        "self_transfers": {
            vertex.identifier: count for vertex, count in evidence.self_transfers
        },
        "composition": None,
        "conclusion": "partial contraction preserves singleton pseudonyms, direction and folded transfer attributes",
        "limitations": list(report.limitations),
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
        raise VerificationError("unsupported pseudonym-graph artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh contraction execution")
    return measured


def render_markdown(artifact):
    rows = [
        f"| {edge['source']} | {edge['target']} | {edge['transfers']} | "
        f"{edge['value']} | {edge['first_height']}–{edge['last_height']} |"
        for edge in artifact["edges"]
    ]
    return "\n".join([
        "# Partial-clustering pseudonym graph",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"Vertices: {', '.join(artifact['vertices'])}.",
        "",
        "| source | target | transfers | value | height span |",
        "|---|---|---:|---:|---|",
        *rows,
        "",
        "The unknown address `z` remains a singleton pseudonym. Parallel transfers from "
        "`cluster-a` to `cluster-x` are folded into one directed edge with count, total value "
        "and height span. The reverse direction remains a separate edge; change within "
        "`cluster-a` is recorded as a self-transfer rather than a relationship.",
        "",
        "The supplied clustering is partial. These vertices are pseudonyms, not verified users.",
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
