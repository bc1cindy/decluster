"""Reproduce and verify the exact-oracle differential audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..baselines import oracle_audit
from ..result_artifacts import canonical_json_bytes, write_canonical_json


EXPERIMENT_ID = "exact-oracle-audit-v1"


class VerificationError(ValueError):
    """A stored experiment artifact differs from a fresh computation."""


def build_artifact(*, max_coins=oracle_audit.FAMILY_MAX_COINS):
    import dss

    family = oracle_audit.enumerate_family(max_coins=max_coins)
    report = oracle_audit.audit(family, include_cases=False)
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "parameters": {
            "alphabet": list(oracle_audit.FAMILY_ALPHABET),
            "max_coins": max_coins,
            "min_side": oracle_audit.FAMILY_MIN_SIDE,
            "tolerance": oracle_audit.TOLERANCE,
        },
        "dependencies": {"dss_version": dss.__version__, "dss_revision": dss.__rev__},
        "summary": oracle_audit.manifest_invariants(report),
        "report": report,
    }


def load_artifact(path):
    try:
        with Path(path).open(encoding="utf-8") as source:
            artifact = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read artifact {path}: {exc}") from exc
    if not isinstance(artifact, dict):
        raise VerificationError("artifact root must be an object")
    return artifact


def verify_artifact(artifact):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported exact-oracle artifact identity")
    parameters = artifact.get("parameters")
    if not isinstance(parameters, dict) or set(parameters) != {
        "alphabet", "max_coins", "min_side", "tolerance",
    }:
        raise VerificationError("artifact parameters are incomplete or contain unknown fields")
    expected_fixed = {
        "alphabet": list(oracle_audit.FAMILY_ALPHABET),
        "min_side": oracle_audit.FAMILY_MIN_SIDE,
        "tolerance": oracle_audit.TOLERANCE,
    }
    for key, expected in expected_fixed.items():
        if parameters[key] != expected:
            raise VerificationError(f"unsupported parameter {key}: {parameters[key]!r}")
    max_coins = parameters["max_coins"]
    if isinstance(max_coins, bool) or not isinstance(max_coins, int):
        raise VerificationError("max_coins must be an integer")
    if not oracle_audit.FAMILY_MIN_SIDE * 2 <= max_coins <= oracle_audit.FAMILY_MAX_COINS:
        raise VerificationError("max_coins is outside the supported exact-oracle range")
    measured = build_artifact(max_coins=max_coins)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh exact-oracle audit")
    return measured


SUMMARY_ROWS = (
    ("transactions", "family_size"),
    ("link-matrix entries", "link_matrix_entries"),
    ("entries above exact", "link_matrix_entries_above_exact"),
    ("entries below exact", "link_matrix_entries_below_exact"),
    ("spurious deterministic links", "spurious_deterministic_links"),
    ("missed deterministic links", "missed_deterministic_links"),
    ("mapping-count undercounts", "mapping_count_undercounts"),
    ("mapping-count overcounts", "mapping_count_overcounts"),
)


def render_markdown(artifact):
    summary = artifact["summary"]
    lines = [
        "# Exact-oracle audit", "",
        "Generated from the canonical experiment artifact. Do not edit manually.", "",
        "| quantity | value |", "|---|---:|",
    ]
    lines.extend(f"| {label} | {summary[key]} |" for label, key in SUMMARY_ROWS)
    lines.extend([
        "", f"Link-matrix bound direction: `{summary['link_matrix_bound_direction']}`.", "",
        f"DSS: `{summary['dss_version']}` at revision `{summary['dss_rev']}`.", "",
    ])
    return "\n".join(lines)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--output", required=True)
    run.add_argument("--max-coins", type=int, default=oracle_audit.FAMILY_MAX_COINS)
    verify = commands.add_parser("verify")
    verify.add_argument("--artifact", required=True)
    verify.add_argument("--markdown")
    render = commands.add_parser("render")
    render.add_argument("--artifact", required=True)
    render.add_argument("--output", required=True)
    reproduce = commands.add_parser("reproduce")
    reproduce.add_argument("--artifact", required=True)
    reproduce.add_argument("--markdown", required=True)
    reproduce.add_argument("--max-coins", type=int, default=oracle_audit.FAMILY_MAX_COINS)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    if args.command == "run":
        write_canonical_json(args.output, build_artifact(max_coins=args.max_coins))
    elif args.command == "verify":
        artifact = verify_artifact(load_artifact(args.artifact))
        if (args.markdown is not None
                and Path(args.markdown).read_text(encoding="utf-8") != render_markdown(artifact)):
            raise VerificationError("Markdown differs from the canonical artifact rendering")
    elif args.command == "render":
        artifact = load_artifact(args.artifact)
        Path(args.output).write_text(render_markdown(artifact), encoding="utf-8")
    else:
        artifact = build_artifact(max_coins=args.max_coins)
        write_canonical_json(args.artifact, artifact)
        Path(args.markdown).parent.mkdir(parents=True, exist_ok=True)
        Path(args.markdown).write_text(render_markdown(artifact), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
