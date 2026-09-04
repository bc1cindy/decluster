"""Reproduce the CTP retroactive change-consolidation failure mode."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..domain import CandidateNarrowing, NoSharedCandidates
from ..failure_modes import change_consolidation as failure_mode
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "change-consolidation-v1"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _outcome_name(outcome):
    if isinstance(outcome, CandidateNarrowing):
        return "candidate_narrowing"
    if isinstance(outcome, NoSharedCandidates):
        return "no_shared_candidates"
    raise TypeError(
        f"unsupported change-consolidation outcome: {type(outcome).__name__}"
    )


def build_artifact():
    scenario = failure_mode.ctp_example()
    report = failure_mode.evaluate(scenario)
    intersection = report.channels[1].evidence[0]
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "scenario": {
            "payments": [payment.identifier for payment in scenario.payments],
            "change_outputs": [
                list(output.identifier) for output in scenario.change_outputs
            ],
            "candidate_owners": [
                sorted(owner.identifier for owner in owners)
                for owners in scenario.candidate_owners
            ],
        },
        "result": {
            "candidates_before": intersection.candidates_before,
            "candidates_after": sorted(
                candidate.identifier for candidate in intersection.candidates_after
            ),
            "outcome": _outcome_name(report.outcomes[0]),
            "composition": report.composition,
        },
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
    if (
        artifact.get("schema_version") != 1
        or artifact.get("experiment") != EXPERIMENT_ID
    ):
        raise VerificationError("unsupported change-consolidation artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh failure-mode execution")
    return measured


def render_markdown(artifact):
    result = artifact["result"]
    survivors = (
        ", ".join(f"`{item}`" for item in result["candidates_after"]) or "none"
    )
    return "\n".join([
        "# Change-consolidation failure mode",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "| quantity | value |",
        "|---|---:|",
        f"| candidate owners before consolidation | {result['candidates_before']} |",
        f"| candidate owners after consolidation | {len(result['candidates_after'])} |",
        f"| surviving candidates | {survivors} |",
        f"| outcome | `{result['outcome']}` |",
        "",
        "The linkage requires correct change identification and a valid "
        "common-ownership premise.",
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
