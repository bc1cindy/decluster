"""Reproduce an equal-entropy, different-intersection counterexample."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..failure_modes.entropy_insufficiency import evaluate, paired_examples
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "entropy-insufficiency-v1"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _measurement(scenario):
    report = evaluate(scenario)
    intersection = report.outcomes[0].evidence
    return {
        "entropy_bits": scenario.entropy_bits,
        "initial_candidates": len(scenario.probabilities),
        "observations": len(scenario.observations),
        "surviving_candidates": len(intersection.candidates_after),
    }


def build_artifact():
    brittle, overlapping = paired_examples()
    brittle_measurement = _measurement(brittle)
    overlapping_measurement = _measurement(overlapping)
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "brittle_overlap": brittle_measurement,
        "overlapping_crowd": overlapping_measurement,
        "equal_initial_entropy": (
            brittle_measurement["entropy_bits"]
            == overlapping_measurement["entropy_bits"]
        ),
        "composition": None,
        "conclusion": "equal point entropy does not determine longitudinal intersection resistance",
        "limitations": list(evaluate(brittle).limitations),
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
        raise VerificationError("unsupported entropy-insufficiency artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh failure-mode execution")
    return measured


def render_markdown(artifact):
    brittle = artifact["brittle_overlap"]
    overlapping = artifact["overlapping_crowd"]
    return "\n".join([
        "# Point entropy is not a longitudinal privacy certificate",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "| scenario | initial entropy | initial candidates | observations | survivors |",
        "|---|---:|---:|---:|---:|",
        f"| brittle overlap | {brittle['entropy_bits']:.1f} bits | "
        f"{brittle['initial_candidates']} | {brittle['observations']} | "
        f"{brittle['surviving_candidates']} |",
        f"| overlapping crowd | {overlapping['entropy_bits']:.1f} bits | "
        f"{overlapping['initial_candidates']} | {overlapping['observations']} | "
        f"{overlapping['surviving_candidates']} |",
        "",
        "The initial posteriors are identical. Different overlap between later candidate sets "
        "produces different residual ambiguity.",
        "",
        "This synthetic counterexample falsifies sufficiency. It does not estimate attack "
        "frequency or certify either scenario's privacy.",
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
