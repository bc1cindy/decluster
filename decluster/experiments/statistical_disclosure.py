"""Reproduce statistical disclosure and its background-matched control."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..domain import PersistentCorrespondentRanked
from ..failure_modes.statistical_disclosure import evaluate, paired_examples
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "statistical-disclosure-v1"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _measurement(scenario):
    report = evaluate(scenario)
    evidence = report.channels[0].evidence[0]
    outcome = report.outcomes[0]
    return {
        "batch_size": scenario.batch_size,
        "observations": len(scenario.rounds),
        "scores": {
            correspondent.identifier: score for correspondent, score in evidence.scores
        },
        "unique_top_correspondent": (
            outcome.correspondent.identifier
            if isinstance(outcome, PersistentCorrespondentRanked)
            else None
        ),
        "top_margin": outcome.margin if isinstance(outcome, PersistentCorrespondentRanked) else 0.0,
    }


def build_artifact():
    persistent, control = paired_examples()
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "persistent_correspondent": _measurement(persistent),
        "background_matched_control": _measurement(control),
        "composition": None,
        "conclusion": "repeated target-active rounds recover a persistent correspondent in the threshold-mix model",
        "limitations": list(evaluate(persistent).limitations),
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
        raise VerificationError("unsupported statistical-disclosure artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh failure-mode execution")
    return measured


def render_markdown(artifact):
    persistent = artifact["persistent_correspondent"]
    control = artifact["background_matched_control"]
    rows = []
    for name, measurement in (("persistent correspondent", persistent), ("background-matched control", control)):
        scores = ", ".join(
            f"{correspondent}={score:.2f}"
            for correspondent, score in measurement["scores"].items()
        )
        rows.append(
            f"| {name} | {measurement['observations']} | {measurement['batch_size']} | "
            f"{scores} | {measurement['unique_top_correspondent'] or 'none'} |"
        )
    return "\n".join([
        "# Longitudinal statistical disclosure",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "| scenario | rounds | batch size | estimated target distribution | unique top |",
        "|---|---:|---:|---|---|",
        *rows,
        "",
        "The persistent fixture recovers Alice. The control remains tied because the target "
        "follows the same distribution as the background.",
        "",
        "This is a deterministic reproduction of the threshold-mix estimator. It does not "
        "attribute Bitcoin ownership or measure real-world attack frequency.",
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
