"""Reproduce the forced and underdetermined amount examples from the CTP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..failure_modes.deterministic_partition import evaluate
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "deterministic-partition-v1"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _measurement(inputs, outputs):
    report = evaluate(inputs, outputs)
    evidence = report.channels[0].evidence[0]
    return {
        "inputs": list(inputs),
        "outputs": list(outputs),
        "non_derived_mappings": evidence.mapping_count,
        "unanimous_links": [
            [left.identifier[1], right.identifier[1]] for left, right in evidence.links
        ],
    }


def build_artifact():
    forced = _measurement((1, 3, 20, 50), (4, 70))
    underdetermined = _measurement((1, 2, 3, 4, 5), (7, 8))
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "balance_model": "exact per-block conservation",
        "mapping_family": "Maurer non-derived mappings",
        "forced_partition": forced,
        "underdetermined_control": underdetermined,
        "composition": None,
        "conclusion": "the forced example has one non-derived mapping and four unanimous links, while the underdetermined example has three mappings and no unanimous link",
        "limitations": list(evaluate((1, 3, 20, 50), (4, 70)).limitations),
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
        raise VerificationError("unsupported deterministic-partition artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh failure-mode execution")
    return measured


def render_markdown(artifact):
    forced = artifact["forced_partition"]
    control = artifact["underdetermined_control"]
    return "\n".join([
        "# Amount-constrained deterministic partition",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "| fixture | non-derived mappings | unanimous input-output links |",
        "|---|---:|---:|",
        f"| forced partition | {forced['non_derived_mappings']} | {len(forced['unanimous_links'])} |",
        f"| underdetermined control | {control['non_derived_mappings']} | {len(control['unanimous_links'])} |",
        "",
        "The forced fixture is 0.1 + 0.3 = 0.4 and 2 + 5 = 7, scaled by ten. The control is the CTP's three-way underdetermined 0.7/0.8 example, also scaled by ten.",
        "",
        "Every statement is conditional on exact per-block conservation and the non-derived mapping family. Fees, contextual priors and net-settlement cycles can change admissibility.",
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
        if args.markdown is not None and Path(args.markdown).read_text(
            encoding="utf-8"
        ) != render_markdown(artifact):
            raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
