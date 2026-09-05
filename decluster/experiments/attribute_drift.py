"""Measure projected epoch drift from the frozen Lumen aggregate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..attribute_drift import GAPS, cycle_gain, drift, pearson
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "attribute-drift-v1"
DEFAULT_DATASET = "tests/fixtures/lumen_explorer_data.json"
RESIDUAL = "__all_unpreserved_values__"


class VerificationError(ValueError):
    """The aggregate or stored result violates this experiment's contract."""


def _load(path):
    try:
        with Path(path).open(encoding="utf-8") as source:
            value = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read Lumen aggregate {path}: {exc}") from exc
    required = {"window", "totals", "axis_value_series", "template_series"}
    if not isinstance(value, dict) or not required.issubset(value):
        raise VerificationError("Lumen aggregate lacks epoch-series fields")
    return value


def _series_points(series, epochs, label):
    if not isinstance(series, list) or len(series) != epochs:
        raise VerificationError(f"{label} must contain exactly {epochs} epochs")
    heights = []
    shares = []
    for index, point in enumerate(series):
        if not isinstance(point, dict) or set(point) != {"start_height", "share"}:
            raise VerificationError(f"{label}[{index}] has an invalid schema")
        height, share = point["start_height"], point["share"]
        if not isinstance(height, int) or not isinstance(share, (int, float)):
            raise VerificationError(f"{label}[{index}] has invalid values")
        share = float(share)
        if not 0.0 <= share <= 1.0:
            raise VerificationError(f"{label}[{index}] share is outside [0,1]")
        heights.append(height)
        shares.append(share)
    return heights, shares


def _volumes(source, epochs, expected_heights):
    candidates = [[] for _ in range(epochs)]
    for template, series in sorted(source["template_series"].items()):
        if not isinstance(series, list) or len(series) != epochs:
            raise VerificationError(f"template {template!r} has an invalid epoch count")
        for index, point in enumerate(series):
            if point.get("start_height") != expected_heights[index]:
                raise VerificationError(f"template {template!r} has inconsistent heights")
            matches, share = point.get("matches"), point.get("share")
            if not isinstance(matches, int) or not isinstance(share, (int, float)):
                raise VerificationError(f"template {template!r} has invalid observations")
            if share:
                volume = round(matches / share)
                if volume <= 0 or abs(matches / volume - share) > 1e-12:
                    raise VerificationError(f"template {template!r} cannot reconstruct volume")
                candidates[index].append(volume)
    volumes = []
    for index, values in enumerate(candidates):
        if not values or len(set(values)) != 1:
            raise VerificationError(f"epoch {index} has missing or inconsistent volume estimates")
        volumes.append(values[0])
    return volumes


def build_artifact(dataset=DEFAULT_DATASET):
    source = _load(dataset)
    epochs = source["window"].get("epochs")
    start = source["window"].get("start_height")
    if not isinstance(epochs, int) or epochs < max(GAPS) + 1 or not isinstance(start, int):
        raise VerificationError("invalid epoch window")
    expected_heights = [start + 144 * index for index in range(epochs)]
    if source["window"].get("end_height") != expected_heights[-1] + 143:
        raise VerificationError("epoch heights do not cover the declared end height")
    axes = {}
    selected = {}
    for axis, values in sorted(source["axis_value_series"].items()):
        if not isinstance(values, dict) or not values:
            raise VerificationError(f"axis {axis!r} contains no value series")
        value_shares = {}
        for value, points in sorted(values.items()):
            heights, shares = _series_points(points, epochs, f"{axis}.{value}")
            if heights != expected_heights:
                raise VerificationError(f"axis {axis!r} has inconsistent heights")
            value_shares[value] = shares
        series = []
        for index in range(epochs):
            row = {value: shares[index] for value, shares in value_shares.items()}
            residual = 1.0 - sum(row.values())
            if residual < -1e-12:
                raise VerificationError(f"axis {axis!r} shares exceed one at epoch {index}")
            row[RESIDUAL] = max(0.0, residual)
            series.append(row)
        axes[axis] = series
        selected[axis] = value_shares
    volumes = _volumes(source, epochs, expected_heights)
    if sum(volumes) != source["totals"].get("txs"):
        raise VerificationError("reconstructed epoch volumes do not equal the transaction total")
    rows = []
    for axis, series in axes.items():
        curve = drift(series, GAPS)
        rows.append({
            "axis": axis,
            "preserved_values": sorted(selected[axis]),
            "drift": {str(gap): curve[gap] for gap in GAPS},
            "weekly_gain": cycle_gain(series),
        })
    coupling = []
    for axis, values in selected.items():
        for value, shares in values.items():
            mean_share = sum(shares) / epochs
            if mean_share > 0.01:
                correlation = pearson(volumes, shares)
                coupling.append({
                    "axis": axis,
                    "value": value,
                    "mean_share": mean_share,
                    "pearson_r": correlation,
                    "r_squared": correlation * correlation,
                })
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "window": {
            "start_height": start,
            "end_height": source["window"].get("end_height"),
            "epochs": epochs,
            "transactions": source["totals"].get("txs"),
            "epoch_size_blocks": 144,
        },
        "measurement": {
            "projection": "preserved_values_plus_combined_residual",
            "axes": rows,
            "volume_coupling": coupling,
            "volume_range": {"minimum": min(volumes), "maximum": max(volumes)},
        },
        "limitations": [
            "only 20 value series across 11 axes are preserved",
            "unpreserved values are combined into one residual category per axis",
            "only projected drift is measured; most full-distribution table rows are historical",
            "volume is reconstructed from redundant template match shares rather than stored directly",
            "population drift does not measure per-cluster attribute distinctiveness",
            "the result is diagnostic and does not produce a clustering score",
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
        raise VerificationError("unsupported attribute-drift artifact identity")
    measured = build_artifact(dataset)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh projected-drift execution")
    return measured


def render_markdown(artifact):
    window = artifact["window"]
    lines = [
        "# Projected attribute drift across epochs",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"Window: {window['epochs']} epochs of {window['epoch_size_blocks']} blocks, covering "
        f"{window['transactions']} transactions.",
        "",
        "| axis projection | TV@1 | TV@7 | TV@30 | TV@120 | weekly gain |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in artifact["measurement"]["axes"]:
        curve = row["drift"]
        lines.append(
            f"| {row['axis']} | {curve['1']:.3f} | {curve['7']:.3f} | "
            f"{curve['30']:.3f} | {curve['120']:.3f} | {row['weekly_gain']:.2f} |"
        )
    lines.extend([
        "",
        "Each row uses the explicitly preserved values plus one combined residual category. "
        "This reproduces every rounded historical cell for nlocktime and low_r. The version "
        "projection yields 0.070 rather than the historical 0.071 at gap 120. These projections "
        "are not replacements for unavailable full-distribution rows or the historical 70/85 "
        "volume-coupling summary.",
        "",
    ])
    return "\n".join(lines)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("reproduce", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--artifact", required=True)
        command.add_argument("--markdown", required=True)
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
