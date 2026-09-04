"""Reproduce the Fellegi-Sunter conditional-dependence ablation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ..archive_snapshot import extract_tar_gz
from ..fingerprint_validate import load_blkcache
from ..fs_ablation import run_ablation_study
from ..reproducibility import fingerprint_source
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "fs-ablation-v1"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _evaluate_snapshot(snapshot):
    with TemporaryDirectory(prefix="decluster-fs-ablation-") as temporary:
        cache = extract_tar_gz(snapshot, temporary) / ".blkcache"
        transactions = load_blkcache(str(cache))
        report = run_ablation_study(
            transactions,
            train_fraction=0.7,
            ablation_cap=4000,
            association_cap=8000,
            seed=0,
            cluster_threshold=0.6,
        )
        report["source"] = fingerprint_source(str(cache / "*.json"))
        report["source"]["pattern"] = ".blkcache/*.json"
        report["source"]["transactions"] = len(transactions)
        return report


def build_artifact(snapshot):
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "dataset": "fs-blkcache-2026-09-04-v1",
        "report": _evaluate_snapshot(snapshot),
        "limitations": [
            "address reuse supplies weak labels rather than independent ownership "
            "labels",
            "the block sample is not representative of the whole chain",
            "the association statistic is descriptive rather than causal",
            "input_script_type and input_types_present are duplicates in this sample",
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


def verify_artifact(artifact, snapshot):
    if (
        artifact.get("schema_version") != 1
        or artifact.get("experiment") != EXPERIMENT_ID
    ):
        raise VerificationError("unsupported FS ablation artifact identity")
    measured = build_artifact(snapshot)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    report = artifact["report"]
    association = report["association"]
    pair = association["most_dependent_pairs"][0]
    return "\n".join([
        "# Fellegi–Sunter conditional-dependence ablation",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "| quantity | value |",
        "|---|---:|",
        f"| transactions | {report['source']['transactions']} |",
        f"| baseline AUC | {report['leave_one_out']['baseline']['auc']:.6f} |",
        f"| dependent field groups | {len(association['clusters'])} |",
        f"| most dependent fields | `{'`, `'.join(pair['fields'])}` |",
        f"| phi among matches | {pair['phi_match']:.6f} |",
        f"| phi among non-matches | {pair['phi_non_match']:.6f} |",
        "",
        "Association is measured conditionally on weak-label class and is not causal.",
        "",
    ])


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
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
        artifact = build_artifact(args.snapshot)
        write_canonical_json(args.artifact, artifact)
        destination = Path(args.markdown)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_markdown(artifact), encoding="utf-8")
    else:
        artifact = verify_artifact(load_artifact(args.artifact), args.snapshot)
        if args.markdown is not None:
            actual = Path(args.markdown).read_text(encoding="utf-8")
            if actual != render_markdown(artifact):
                raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
