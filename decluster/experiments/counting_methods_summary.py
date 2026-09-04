"""Compose the counting-method report from canonical experiment artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "counting-methods-v1"
COMPONENTS = {
    "router": (
        "results/artifacts/counting-router-v1.json",
        "counting-router-v1",
        "731164f77a75776fc91a9c5bc8bce16700e6084e44c75d7e83510ac8afec1ce5",
    ),
    "fee_sensitivity": (
        "results/artifacts/counting-fee-sensitivity-v1.json",
        "counting-fee-sensitivity-v1",
        "0fef54735522470634c696ec026c31c86dff4d4dae23da956b49d8f89eb3a508",
    ),
}


class VerificationError(ValueError):
    """An input or generated result violates the composition contract."""


def _load_component(path, expected_experiment, expected_sha256):
    source = Path(path)
    try:
        payload = source.read_bytes()
        value = json.loads(payload)
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read component {path}: {exc}") from exc
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_sha256:
        raise VerificationError(
            f"component {path} has SHA-256 {digest}, expected {expected_sha256}"
        )
    if not isinstance(value, dict) or value.get("experiment") != expected_experiment:
        raise VerificationError(f"component {path} has the wrong experiment identity")
    return value


def build_artifact(paths=None):
    paths = paths or {name: specification[0] for name, specification in COMPONENTS.items()}
    loaded = {}
    identities = {}
    for name, (_default, experiment, digest) in COMPONENTS.items():
        loaded[name] = _load_component(paths[name], experiment, digest)
        identities[name] = {"experiment": experiment, "sha256": digest}
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "components": identities,
        "router": loaded["router"]["report"],
        "fee_sensitivity": {
            "fixture": loaded["fee_sensitivity"]["fixture"],
            "observations": loaded["fee_sensitivity"]["observations"],
        },
        "excluded_historical_measurements": [
            {
                "measurement": "wall-clock benchmarks",
                "reason": "no pinned machine and resource protocol supports comparison",
            },
            {
                "measurement": "seven L candidates over 18 synthetic instances",
                "reason": "the instance-generation recipe and seeds were not preserved",
            },
            {
                "measurement": "obsolete router shares",
                "reason": "the current canonical router run supersedes earlier revisions",
            },
        ],
        "limitations": [
            "this artifact composes upstream results and performs no counting calculation",
            "component SHA-256 identities are mandatory",
            "runtime benchmarks require a separate benchmark protocol",
            "an L-estimator comparison requires a preserved generator and seeds",
            "the counting objects remain diagnostics and are not a privacy score or CoinScore",
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


def verify_artifact(artifact, *, paths=None):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported counting-methods summary identity")
    measured = build_artifact(paths)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from the canonical component composition")
    return measured


def render_markdown(artifact):
    router = artifact["router"]["current_router"]
    routes = router["by_method_and_kind"]
    population = artifact["router"]["population"]["multi_input_transactions"]
    observations = artifact["fee_sensitivity"]["observations"]
    first_unmeasured = next(
        row["fee_sat"] for row in observations if not row["measured_input_indices"]
    )
    return "\n".join([
        "# Counting-method observations",
        "",
        "Generated only from two SHA-256-pinned canonical artifacts. Do not edit manually.",
        "",
        f"The current router evaluates {population:,} complete multi-input transactions. It "
        f"returns {routes.get('radix:exact', 0):,} radix exact, "
        f"{routes.get('sparse:exact', 0):,} sparse exact and "
        f"{routes.get('sparse:lower_bound', 0):,} sparse lower-bound outcomes. "
        f"It refuses {routes.get('none:unknown', 0):,} transactions.",
        "",
        f"In the fixed fee fixture, the per-coin interface first measures no input at "
        f"{first_unmeasured:,} sat while the transaction router remains defined. These are "
        "different counting objects and cannot substitute for one another.",
        "",
        "Historical wall-clock timings and the 18-case L comparison are excluded because their "
        "benchmark protocol and synthetic generator were not preserved. Earlier router shares "
        "are superseded by the current run.",
        "",
        "These observations are diagnostics, not mapping entropy, a privacy score or CoinScore.",
        "",
    ])


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    for name, (default, _experiment, _digest) in COMPONENTS.items():
        parser.add_argument(f"--{name.replace('_', '-')}", default=default)
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
    paths = {name: getattr(args, name) for name in COMPONENTS}
    if args.command == "reproduce":
        artifact = build_artifact(paths)
        write_canonical_json(args.artifact, artifact)
        destination = Path(args.markdown)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_markdown(artifact), encoding="utf-8")
    else:
        artifact = verify_artifact(load_artifact(args.artifact), paths=paths)
        if args.markdown is not None:
            actual = Path(args.markdown).read_text(encoding="utf-8")
            if actual != render_markdown(artifact):
                raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
