"""Reproduce the CTP Eve–Alice–Eve consolidation failure mode."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..domain import CandidateNarrowing, Inconclusive
from ..failure_modes import eve_alice_eve as failure_mode
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "eve-alice-eve-v1"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _outcome_name(outcome):
    if isinstance(outcome, CandidateNarrowing):
        return "candidate_narrowing"
    if isinstance(outcome, Inconclusive):
        return "inconclusive"
    raise TypeError(f"unsupported Eve-Alice-Eve outcome: {type(outcome).__name__}")


def _result(report):
    outcome = report.outcomes[0]
    candidates_after = []
    if isinstance(outcome, CandidateNarrowing):
        candidates_after = sorted(
            candidate.identifier for candidate in outcome.evidence.candidates_after
        )
    return {
        "observations": len(report.subjects) - 1,
        "outcome": _outcome_name(outcome),
        "candidates_after": candidates_after,
        "composition": report.composition,
    }


def build_artifact():
    consolidated = failure_mode.ctp_consolidation_example()
    isolated = failure_mode.CounterpartyReturnScenario(
        consolidated.counterparty,
        consolidated.deposited_inputs[:1],
        consolidated.candidate_customers[:1],
    )
    isolated_report = failure_mode.evaluate(isolated)
    consolidated_report = failure_mode.evaluate(consolidated)
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "adversary": "counterparty with private transaction records",
        "isolated_return": _result(isolated_report),
        "consolidated_return": _result(consolidated_report),
        "limitations": list(consolidated_report.limitations),
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
        raise VerificationError("unsupported Eve-Alice-Eve artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh failure-mode execution")
    return measured


def render_markdown(artifact):
    isolated = artifact["isolated_return"]
    consolidated = artifact["consolidated_return"]
    survivors = ", ".join(
        f"`{item}`" for item in consolidated["candidates_after"]
    )
    return "\n".join([
        "# Eve–Alice–Eve consolidation failure mode",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "| observation | inputs | outcome | surviving candidates |",
        "|---|---:|---|---|",
        f"| isolated return | {isolated['observations']} | "
        f"`{isolated['outcome']}` | none |",
        f"| consolidated return | {consolidated['observations']} | "
        f"`{consolidated['outcome']}` | {survivors} |",
        "",
        "The counterparty's records strengthen its observation, but candidate "
        "narrowing is not identity attribution.",
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
