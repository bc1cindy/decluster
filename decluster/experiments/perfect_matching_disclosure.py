"""Reproduce the defining PMDA joint-assignment mechanism and a tied control."""

from __future__ import annotations

import argparse
import json
from math import exp
from pathlib import Path

from ..domain import MessageAssignmentRecovered
from ..failure_modes.perfect_matching_disclosure import evaluate, paired_examples
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "perfect-matching-disclosure-v1"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _positions(scenario, assignment):
    receiver_positions = {receiver: index for index, receiver in enumerate(scenario.receivers)}
    return [receiver_positions[receiver] for _, receiver in assignment]


def _measurement(scenario):
    report = evaluate(scenario)
    evidence = report.channels[0].evidence[0]
    outcome = report.outcomes[0]
    assignments = getattr(evidence, "optimal_assignments", ())
    log_likelihood = getattr(evidence, "log_likelihood", None)
    naive = [max(range(len(row)), key=row.__getitem__) for row in scenario.profile_weights]
    return {
        "messages": len(scenario.senders),
        "naive_receiver_positions": naive,
        "naive_is_bijective": len(set(naive)) == len(naive),
        "optimal_assignments": [
            _positions(scenario, assignment) for assignment in assignments
        ],
        "optimal_assignment_count": len(assignments),
        "joint_likelihood": exp(log_likelihood) if log_likelihood is not None else None,
        "unique_assignment_recovered": isinstance(outcome, MessageAssignmentRecovered),
    }


def build_artifact():
    joint, control = paired_examples()
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "joint_assignment": _measurement(joint),
        "uniform_profile_control": _measurement(control),
        "composition": None,
        "conclusion": "joint perfect matching resolves a round that independent per-message maxima cannot assign bijectively",
        "limitations": list(evaluate(joint).limitations),
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
        raise VerificationError("unsupported perfect-matching artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh failure-mode execution")
    return measured


def render_markdown(artifact):
    joint = artifact["joint_assignment"]
    control = artifact["uniform_profile_control"]
    return "\n".join([
        "# Perfect-matching disclosure",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "| scenario | naive assignment | naive bijective | optimal matchings | unique optimum |",
        "|---|---|---:|---:|---:|",
        f"| joint assignment | {joint['naive_receiver_positions']} | "
        f"{str(joint['naive_is_bijective']).lower()} | {joint['optimal_assignment_count']} | "
        f"{str(joint['unique_assignment_recovered']).lower()} |",
        f"| uniform-profile control | {control['naive_receiver_positions']} | "
        f"{str(control['naive_is_bijective']).lower()} | {control['optimal_assignment_count']} | "
        f"{str(control['unique_assignment_recovered']).lower()} |",
        "",
        "The joint fixture has the unique sender-to-receiver position assignment [0, 1, 2]. "
        "Independent maxima reuse receiver 0 and therefore do not form a matching. The uniform "
        "control retains all six perfect matchings.",
        "",
        "Profiles are supplied. This fixture tests the defining within-round PMDA objective, not "
        "longitudinal profile estimation, Bitcoin value flow, or ownership attribution.",
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
