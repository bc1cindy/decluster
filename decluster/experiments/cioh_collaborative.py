"""Reproduce the CIOH false merge on a labelled collaborative fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..domain import ClusterMerge, ReferenceOwnershipConflict
from ..failure_modes.cioh_collaborative import evaluate
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "cioh-collaborative-false-merge-v1"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _measurement(owner_by_coin):
    report = evaluate("collaborative-spend", owner_by_coin)
    return {
        "inputs": len(owner_by_coin),
        "predicted_merges": sum(isinstance(item, ClusterMerge) for item in report.outcomes),
        "reference_conflicts": sum(
            isinstance(item, ReferenceOwnershipConflict) for item in report.outcomes
        ),
    }


def build_artifact():
    collaborative = _measurement({"alice-input": "alice", "bob-input": "bob"})
    unilateral = _measurement({"alice-input-1": "alice", "alice-input-2": "alice"})
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "collaborative": collaborative,
        "same_owner_control": unilateral,
        "composition": None,
        "conclusion": "CIOH merges both co-spends, but only the labelled collaborative fixture conflicts with its supplied ownership partition",
        "limitations": list(
            evaluate(
                "collaborative-spend", {"alice-input": "alice", "bob-input": "bob"}
            ).limitations
        ),
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
        raise VerificationError("unsupported CIOH collaborative artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh failure-mode execution")
    return measured


def render_markdown(artifact):
    collaborative = artifact["collaborative"]
    control = artifact["same_owner_control"]
    return "\n".join([
        "# CIOH false merge in a collaborative transaction",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "| fixture | inputs | predicted merges | reference conflicts |",
        "|---|---:|---:|---:|",
        f"| collaborative | {collaborative['inputs']} | {collaborative['predicted_merges']} | {collaborative['reference_conflicts']} |",
        f"| same-owner control | {control['inputs']} | {control['predicted_merges']} | {control['reference_conflicts']} |",
        "",
        "CIOH observes only the co-spend and therefore merges both pairs. The collaborative fixture's supplied participant labels expose that merge as false.",
        "",
        "The labels are part of the deterministic fixture. This result does not estimate chain-wide prevalence or infer real ownership.",
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
