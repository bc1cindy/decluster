"""Reconstruct fingerprint class sizes from the frozen Lumen aggregate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..fingerprint_sparsity import LABELS, reconstruct_histogram
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "fingerprint-sparsity-v1"
DEFAULT_DATASET = "tests/fixtures/lumen_explorer_data.json"


class VerificationError(ValueError):
    """The aggregate or stored result violates this experiment's contract."""


def _load(path):
    try:
        with Path(path).open(encoding="utf-8") as source:
            value = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read Lumen aggregate {path}: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("cond"), dict):
        raise VerificationError("Lumen aggregate must contain conditional histograms")
    return value


def build_artifact(dataset=DEFAULT_DATASET):
    source = _load(dataset)
    expected_total = source.get("totals", {}).get("txs")
    if isinstance(expected_total, bool) or not isinstance(expected_total, int):
        raise VerificationError("Lumen aggregate has no integer transaction total")
    reconstructions = {}
    for axis in sorted(source["cond"]):
        try:
            histogram, total = reconstruct_histogram(source["cond"][axis])
        except ValueError as exc:
            raise VerificationError(f"invalid conditional histogram for {axis}: {exc}") from exc
        if total != expected_total:
            raise VerificationError(
                f"conditional histogram for {axis} covers {total}, expected {expected_total}"
            )
        reconstructions[axis] = histogram
    if not reconstructions:
        raise VerificationError("Lumen aggregate contains no conditional axes")
    first_axis = next(iter(reconstructions))
    histogram = reconstructions[first_axis]
    disagreeing = [axis for axis, candidate in reconstructions.items() if candidate != histogram]
    if disagreeing:
        raise VerificationError(f"conditional axes disagree with {first_axis}: {disagreeing}")
    shares = {label: histogram[label] / expected_total for label in LABELS}
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "window": {
            "start_height": source.get("window", {}).get("start_height"),
            "end_height": source.get("window", {}).get("end_height"),
            "epochs": source.get("window", {}).get("epochs"),
            "transactions": expected_total,
        },
        "measurement": {
            "vector_width": 12,
            "scope": "whole_window",
            "class_size_counts": histogram,
            "class_size_shares": shares,
            "share_below_10": shares["exactly 1"] + shares["2-9"],
            "share_below_100": shares["exactly 1"] + shares["2-9"] + shares["10-99"],
        },
        "cross_check": {"consistent_conditional_partitions": sorted(reconstructions)},
        "limitations": [
            "the fixture contains aggregate histograms rather than transaction-level vectors",
            "the 19-axis and per-epoch distributions are not preserved and are not reproduced",
            "exact-vector class size is not nearest-neighbour sparsity in a general feature metric",
            "the result concerns per-transaction vectors, not cluster feature distributions",
            "the scan ends at height 962720 and differs by 6219 records from the cataloged raw export",
            "the dataset publisher authorized redistribution of the aggregate fixture on 2026-09-04",
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


def verify_artifact(artifact, dataset=DEFAULT_DATASET):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported fingerprint-sparsity artifact identity")
    measured = build_artifact(dataset)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh aggregate reconstruction")
    return measured


def render_markdown(artifact):
    window = artifact["window"]
    measurement = artifact["measurement"]
    shares = measurement["class_size_shares"]
    lines = [
        "# Fingerprint exact-vector class sizes",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"Window: blocks {window['start_height']} through {window['end_height']}; "
        f"{window['transactions']} transactions in {window['epochs']} epochs.",
        "",
        "| class size | transaction share |",
        "|---|---:|",
    ]
    lines.extend(f"| {label} | {shares[label] * 100:.3f}% |" for label in LABELS)
    lines.extend([
        "",
        f"Share below 10: {measurement['share_below_10'] * 100:.3f}%.",
        f"Share below 100: {measurement['share_below_100'] * 100:.3f}%.",
        "",
        "All preserved conditional partitions reconstruct the same 12-axis whole-window "
        "histogram. The unavailable 19-axis and per-epoch columns are excluded. Exact-vector "
        "equivalence classes do not establish general metric sparsity or successful attribution.",
        "",
    ])
    return "\n".join(lines)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    commands = parser.add_subparsers(dest="command", required=True)
    reproduce = commands.add_parser("reproduce")
    reproduce.add_argument("--artifact", required=True)
    reproduce.add_argument("--markdown", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--artifact", required=True)
    verify.add_argument("--markdown", required=True)
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
        artifact = verify_artifact(load_artifact(args.artifact), args.dataset)
        if Path(args.markdown).read_text(encoding="utf-8") != render_markdown(artifact):
            raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
