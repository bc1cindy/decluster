"""Reproduce the executable boundary of the N-S 2011 baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..baselines.ns_link_prediction_2011 import (
    ComponentStatus,
    IncompletePipelineError,
    PipelineComponent,
    pipeline_coverage,
    require_components,
)
from ..result_artifacts import canonical_json_bytes, write_canonical_json


EXPERIMENT_ID = "ns-link-prediction-coverage-v2"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _refusal(component: PipelineComponent) -> str:
    try:
        require_components(component)
    except IncompletePipelineError as exc:
        return str(exc)
    raise RuntimeError(f"expected {component.value} to be refused")


def build_artifact() -> dict:
    coverage = pipeline_coverage()
    implemented = tuple(
        row.component for row in coverage if row.status is ComponentStatus.IMPLEMENTED
    )
    require_components(*implemented)
    unavailable = tuple(
        row.component for row in coverage if row.status is not ComponentStatus.IMPLEMENTED
    )
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "paper": "Narayanan-Shi-Rubinstein-2011",
        "components": [
            {
                "component": row.component.value,
                "status": row.status.value,
                "limitation": row.limitation,
            }
            for row in coverage
        ],
        "implemented_gate": {
            "accepted": True,
            "components": [component.value for component in implemented],
        },
        "refusal_controls": {
            component.value: _refusal(component) for component in unavailable
        },
        "end_to_end_reproduced": False,
        "composition": None,
        "conclusion": (
            "implemented components do not constitute the complete published pipeline"
        ),
        "limitations": [
            "the published Flickr/Kaggle corpus and reported metrics are not reproduced",
            "the zero convention for dummy-incident terms is read from the paper's prose, "
            "not from its formula",
            "annealing uses explicit local reproducibility controls",
            "confidence pruning, accepted-mapping correction and the learned 25-feature model "
            "are not reproduced",
        ],
    }


def load_artifact(path: str | Path) -> dict:
    try:
        with Path(path).open(encoding="utf-8") as source:
            value = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerificationError("artifact root must be an object")
    return value


def verify_artifact(artifact: dict) -> dict:
    if (artifact.get("schema_version"), artifact.get("experiment")) != (
        1,
        EXPERIMENT_ID,
    ):
        raise VerificationError("unsupported N-S coverage artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh coverage execution")
    return measured


def render_markdown(artifact: dict) -> str:
    lines = [
        "# N-S 2011 executable coverage",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "| component | status | limitation |",
        "|---|---|---|",
    ]
    lines.extend(
        f"| `{row['component']}` | `{row['status']}` | {row['limitation'] or '—'} |"
        for row in artifact["components"]
    )
    lines.extend([
        "",
        "Every non-implemented component is exercised through the refusal gate. The implemented "
        "components pass that gate, but the end-to-end paper pipeline remains unreproduced.",
        "",
        "This deterministic contract does not reproduce the Flickr/Kaggle corpus, reported "
        "metrics, dummy-node convention, pruning policy, correction schedule, or learned model.",
        "",
    ])
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    reproduce = commands.add_parser("reproduce")
    reproduce.add_argument("--artifact", required=True)
    reproduce.add_argument("--markdown", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--artifact", required=True)
    verify.add_argument("--markdown")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "reproduce":
        artifact = build_artifact()
        write_canonical_json(args.artifact, artifact)
        markdown = Path(args.markdown)
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(render_markdown(artifact), encoding="utf-8")
    else:
        artifact = verify_artifact(load_artifact(args.artifact))
        if args.markdown is not None:
            try:
                actual = Path(args.markdown).read_text(encoding="utf-8")
            except OSError as exc:
                raise VerificationError(f"cannot read Markdown {args.markdown}: {exc}") from exc
            if actual != render_markdown(artifact):
                raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
