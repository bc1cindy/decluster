"""Reproduce additive decay and provenance graph fracture separately."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..domain import GraphFractureMeasured, Inconclusive
from ..failure_modes import provenance_decay as failure_mode
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "provenance-decay-v1"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _measurement(report):
    elimination = report.channels[0].evidence[0]
    structural = report.outcomes[1]
    result = {
        "candidates_before": len(elimination.candidates_before),
        "candidates_after": len(elimination.candidates_after),
        "structural_outcome": (
            "graph_fracture"
            if isinstance(structural, GraphFractureMeasured)
            else "inconclusive"
        ),
    }
    if isinstance(structural, GraphFractureMeasured):
        result["components_before"] = structural.evidence.components_before
        result["components_after"] = structural.evidence.components_after
    elif not isinstance(structural, Inconclusive):
        raise TypeError(f"unsupported structural outcome: {type(structural).__name__}")
    return result


def build_artifact():
    bridge = failure_mode.ctp_fracture_example()
    peripheral = next(
        node for node in bridge.graph_nodes if node.identifier == "left-origin"
    )
    control = failure_mode.ProvenanceDecayScenario(
        bridge.target,
        bridge.candidates,
        frozenset({peripheral}),
        bridge.graph_nodes,
        bridge.graph_edges,
    )
    bridge_report = failure_mode.evaluate(bridge)
    control_report = failure_mode.evaluate(control)
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "bridge_removal": _measurement(bridge_report),
        "peripheral_removal": _measurement(control_report),
        "composition": None,
        "limitations": list(bridge_report.limitations),
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
        raise VerificationError("unsupported provenance-decay artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh failure-mode execution")
    return measured


def render_markdown(artifact):
    bridge = artifact["bridge_removal"]
    control = artifact["peripheral_removal"]
    return "\n".join([
        "# Provenance decay failure modes",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "| removal | candidates | structural outcome | components |",
        "|---|---:|---|---:|",
        f"| bridge | {bridge['candidates_before']} → {bridge['candidates_after']} | "
        f"`{bridge['structural_outcome']}` | "
        f"{bridge['components_before']} → {bridge['components_after']} |",
        f"| peripheral | {control['candidates_before']} → "
        f"{control['candidates_after']} | `{control['structural_outcome']}` | "
        "unchanged |",
        "",
        "Equal additive elimination does not imply equal structural decay.",
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
