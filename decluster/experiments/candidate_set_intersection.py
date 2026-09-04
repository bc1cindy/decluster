"""Reproduce the deterministic candidate-set intersection fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..baselines import candidate_set_intersection as baseline
from ..result_artifacts import canonical_json_bytes, write_canonical_json


EXPERIMENT_ID = "candidate-set-intersection-v1"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _serialize_step(step):
    return {
        "index": step.index,
        "observed": step.observed,
        "before": step.before,
        "after": step.after,
        "narrowing_bits": step.narrowing_bits,
    }


def build_artifact():
    scenarios = []
    for name, observations in baseline.scenarios():
        result = baseline.intersect_candidate_sets(
            observations, universe_size=baseline.UNIVERSE
        )
        scenarios.append({
            "name": name,
            "observations": [sorted(observation) for observation in observations],
            "steps": [_serialize_step(step) for step in result.steps],
            "surviving": sorted(result.surviving),
            "narrowing_bits": result.narrowing_bits,
            "identified": result.identified,
            "inconsistent_at": result.inconsistent_at,
        })
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "parameters": {"universe_size": baseline.UNIVERSE},
        "scenarios": scenarios,
        "summary": baseline.manifest_invariants(),
        "limitations": [
            "synthetic fixture",
            "candidate sets are supplied rather than inferred from chain data",
            "the run validates the abstract intersection mechanism, not JoinMarket detection",
            "no empirical rate is attributed to Goldfeder et al.",
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
        raise VerificationError("unsupported candidate-set intersection artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh fixture execution")
    return measured


def render_markdown(artifact):
    rows = []
    for scenario in artifact["scenarios"]:
        identified = scenario["identified"]
        rows.append(
            f"| {scenario['name']} | {len(scenario['surviving'])} | "
            f"{scenario['narrowing_bits']} | {identified} | "
            f"{scenario['inconsistent_at']} |"
        )
    return "\n".join([
        "# Candidate-set intersection fixture",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "| scenario | survivors | narrowing bits | identified | inconsistent at |",
        "|---|---:|---:|---:|---:|",
        *rows,
        "",
        "This synthetic run validates the abstract intersection mechanism. It does not measure "
        "JoinMarket or Bitcoin deanonymization rates.",
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
