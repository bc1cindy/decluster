"""Reproduce the bounded exact-versus-fee-allocation audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from examples import boltzmann_fee_audit as legacy

from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "boltzmann-fee-audit-v1"
DATASET = "data/boltzmann-fee-audit-v1.json"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def build_artifact(dataset=DATASET):
    report = legacy.audit(dataset, cap=300, max_coins=8)
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "corpus": "bounded public Bitcoin transaction snapshot",
        "report": report,
        "limitations": [
            "the selected population is deterministic but not chain-representative",
            "the all-coins interpretation makes fee-tolerant acceptance non-informative",
            "fee roundness is reported but is not a competing probability model",
            "this audit measures the local fee-allocation model, not general parity with Boltzmann",
            "separate tests cover selected official Boltzmann vectors and modes",
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


def verify_artifact(artifact, *, dataset=DATASET):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported Boltzmann fee-audit artifact identity")
    measured = build_artifact(dataset)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    report = artifact["report"]
    population = report["population"]
    outcomes = report["outcomes"]
    return "\n".join([
        "# Exact conservation versus explicit fee allocation",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"The bounded population contains {population['selected']} transactions. Exact "
        f"zero-fee conservation admits mappings for {outcomes['exact_with_mapping']}; "
        f"the local fee-allocation model admits mappings for "
        f"{outcomes['fee_tolerant_with_mapping']}.",
        "",
        f"Only {outcomes['fee_tolerant_with_nontrivial_split']} transactions admit more "
        "than the all-coins interpretation. This is the informative comparison.",
        "",
        "This run is not a claim of general parity with the external Boltzmann tool. "
        "Selected official vectors and modes are tested separately.",
        "",
    ])


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DATASET)
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
        artifact = build_artifact(args.dataset)
        write_canonical_json(args.artifact, artifact)
        destination = Path(args.markdown)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_markdown(artifact), encoding="utf-8")
    else:
        artifact = verify_artifact(load_artifact(args.artifact), dataset=args.dataset)
        if args.markdown is not None:
            actual = Path(args.markdown).read_text(encoding="utf-8")
            if actual != render_markdown(artifact):
                raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
