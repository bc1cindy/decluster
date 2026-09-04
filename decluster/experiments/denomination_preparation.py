"""Reproduce a fixed-denomination predecessor fingerprint on paired fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..domain import TransactionFingerprintObserved
from ..failure_modes.denomination_preparation import evaluate, paired_corpus
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "denomination-preparation-v1"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _measurement(observations):
    reports = tuple(evaluate(observation) for observation in observations)
    return {
        "transactions": len(reports),
        "fingerprint_matches": sum(
            isinstance(report.outcomes[0], TransactionFingerprintObserved)
            for report in reports
        ),
        "features": [
            dict(report.channels[0].evidence[0].features) for report in reports
        ],
    }


def build_artifact():
    preparations, controls = paired_corpus()
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "preparations": _measurement(preparations),
        "arity_matched_controls": _measurement(controls),
        "composition": None,
        "conclusion": "an exact denomination consumed by the next CoinJoin distinguishes the synthetic preparations from arity-matched controls",
        "limitations": list(evaluate(preparations[0]).limitations),
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
        raise VerificationError("unsupported denomination-preparation artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh failure-mode execution")
    return measured


def render_markdown(artifact):
    preparations = artifact["preparations"]
    controls = artifact["arity_matched_controls"]
    return "\n".join([
        "# Fixed-denomination preparation fingerprint",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "| population | transactions | fingerprint matches |",
        "|---|---:|---:|",
        f"| synthetic preparations | {preparations['transactions']} | "
        f"{preparations['fingerprint_matches']} |",
        f"| arity-matched controls | {controls['transactions']} | "
        f"{controls['fingerprint_matches']} |",
        "",
        "The rule observes one exact-denomination predecessor output consumed by the declared "
        "next CoinJoin. Controls have the same input and output counts.",
        "",
        "This construction-level fixture does not measure prevalence and does not prove that a "
        "matched predecessor is unilateral or commonly owned.",
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
