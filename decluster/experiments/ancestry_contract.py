"""Measure the nominal-value provenance and typed ancestry contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..adaptations.ancestry import (
    CompleteAncestry,
    TruncatedAncestry,
    ancestry_signature_report,
)
from ..ancestry import provenance_link, value_flow_untraceability
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "ancestry-contract-v1"
TARGET = ("target", 0)


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


TRANSACTIONS = {
    "target": {
        "vin": [
            {"txid": "left", "vout": 0, "prevout": {"value": 5}},
            {"txid": "right", "vout": 0, "prevout": {"value": 5}},
        ],
        "vout": [{"value": 9}],
    },
    "left": {"vin": [{"is_coinbase": True}], "vout": [{"value": 5}]},
    "right": {"vin": [{"is_coinbase": True}], "vout": [{"value": 5}]},
}


def _fetch(txid):
    return TRANSACTIONS[txid]


def _distribution(report):
    return {
        f"{subject.identifier[0]}:{subject.identifier[1]}": round(mass, 15)
        for subject, mass in report.distribution
    }


def _truncation(report):
    return {
        "oracle_refused": report.truncation.oracle_refused,
        "node_capped": report.truncation.node_capped,
        "zero_link_mass": report.truncation.zero_link_mass,
        "unattributed": report.truncation.unattributed,
    }


def build_artifact():
    complete = ancestry_signature_report(TARGET, depth=2, fetch=_fetch)
    capped = ancestry_signature_report(TARGET, depth=2, fetch=_fetch, max_nodes=1)
    refused = ancestry_signature_report(
        TARGET, depth=2, fetch=_fetch, link_oracle=lambda _inputs, _outputs: None,
    )
    nominal = value_flow_untraceability(TARGET, depth=2, fetch=_fetch)
    signature, _support = complete.as_legacy()
    disjoint = {("unrelated", 0): 1.0}

    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "fixture": {"transactions": len(TRANSACTIONS), "target": "target:0", "depth": 2},
        "complete": {
            "state": type(complete.state).__name__,
            "is_complete": isinstance(complete.state, CompleteAncestry),
            "distribution": _distribution(complete),
            "truncation": _truncation(complete),
            "shannon_bits": round(nominal["untraceability"], 15),
            "expected_paper_steps": nominal["expected_steps"],
        },
        "bounded": {
            "state": type(capped.state).__name__,
            "is_truncated": isinstance(capped.state, TruncatedAncestry),
            "truncation": _truncation(capped),
        },
        "oracle_refusal": {
            "state": type(refused.state).__name__,
            "is_truncated": isinstance(refused.state, TruncatedAncestry),
            "truncation": _truncation(refused),
        },
        "overlap": {
            "self": provenance_link(signature, signature),
            "disjoint": provenance_link(signature, disjoint),
        },
        "capabilities": {
            "nominal_value_transition": True,
            "absorbing_distribution": True,
            "typed_complete_and_truncated_states": True,
            "truncation_causes_separated": True,
            "provenance_overlap_diagnostic": True,
        },
        "limitations": [
            "the fixture is synthetic and validates mechanism contracts",
            "the nominal-value model does not infer ownership or payment allocation",
            "provenance overlap is model-relative evidence, not attribution",
            "the run does not reproduce the historical DSS or live Bitcoin measurements",
            "the outputs are not robust connectivity, a privacy certificate or CoinScore",
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
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported ancestry-contract artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh contract execution")
    return measured


def render_markdown(artifact):
    complete = artifact["complete"]
    capped = artifact["bounded"]
    refused = artifact["oracle_refusal"]
    overlap = artifact["overlap"]
    return "\n".join([
        "# Nominal-value ancestry contract",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"The complete walk reaches `{complete['distribution']}` with Shannon entropy "
        f"{complete['shannon_bits']:.6f} bits and "
        f"{complete['expected_paper_steps']:.1f} steps in the uncollapsed paper graph.",
        "",
        f"A one-node bound returns `{capped['state']}` with causes "
        f"`{capped['truncation']}`. Oracle refusal returns `{refused['state']}` with causes "
        f"`{refused['truncation']}`.",
        "",
        f"Provenance overlap is {overlap['self']:.1f} for the same signature and "
        f"{overlap['disjoint']:.1f} for a disjoint signature.",
        "",
        "This measures model-relative provenance. It does not infer ownership, certify privacy, "
        "measure robust connectivity or reproduce the historical live Bitcoin observations.",
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
