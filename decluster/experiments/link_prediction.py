"""Reproduce the planted-view link-prediction experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from examples import link_prediction_run as legacy

from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "link-prediction-v1"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def build_artifact():
    args = legacy.build_parser().parse_args([])
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "corpus": "deterministic planted-view fixtures",
        "report": legacy.build_report(args),
        "limitations": [
            "synthetic corpus",
            "seeds are sampled from the withheld correspondence",
            "this is not a reproduction of the 2011 paper or Kaggle/Flickr results",
            "the measured advantage transfers links observed by the auxiliary view",
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
    if (
        artifact.get("schema_version") != 1
        or artifact.get("experiment") != EXPERIMENT_ID
    ):
        raise VerificationError("unsupported link-prediction artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def _attack_rows(artifact):
    return [fixture["runs"][0] for fixture in artifact["report"]["fixtures"]]


def render_markdown(artifact):
    rows = _attack_rows(artifact)
    lines = [
        "# Link prediction on planted views",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "| seed | de-anonymization AUC | structure-only AUC | verdict |",
        "|---:|---:|---:|---|",
    ]
    for fixture, row in zip(artifact["report"]["fixtures"], rows):
        lines.append(
            f"| {fixture['fixture_seed']} | {row['deanonymization']['auc']:.6f} | "
            f"{row['structure_only']['auc']:.6f} | "
            f"`{row['separability']['beats_structure_only']}` |"
        )
    lines.extend([
        "",
        "This synthetic result transfers links already observed in the auxiliary view. "
        "It is not a reproduction of the 2011 paper or its datasets.",
        "",
    ])
    return "\n".join(lines)


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
