"""Reproduce the global fingerprint-weight sensitivity sweep."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ..archive_snapshot import extract_tar_gz
from ..fingerprint_validate import load_blkcache
from ..reproducibility import fingerprint_source
from ..result_artifacts import canonical_json_bytes, write_canonical_json
from ..weight_sensitivity import sweep

EXPERIMENT_ID = "weight-sensitivity-v1"


class VerificationError(ValueError):
    """The stored result differs from a fresh execution."""


def build_artifact(snapshot):
    with TemporaryDirectory(prefix="decluster-weight-") as temporary:
        root = extract_tar_gz(snapshot, temporary)
        cache = root / ".blkcache"
        transactions = load_blkcache(str(cache))
        measurement = sweep(transactions)
        source = fingerprint_source(str(cache / "*.json"))
        source.update(pattern=".blkcache/*.json", transactions=len(transactions))
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "dataset": "fs-blkcache-2026-09-04-v1",
        "source": source,
        "measurement": measurement,
        "historical_comparison": {
            "status": "partially_falsified",
            "preserved": "AUC changes little from consistency 0.90 through 0.99",
            "falsified": "AUC is not monotone and consistency 0.99 does not improve on 0.95",
        },
        "limitations": [
            "address reuse is a weak and partly feature-dependent ownership proxy",
            "the sweep varies one global value rather than fitting each axis",
            "the same selected sample is reused at every grid point",
            "the snapshot is not representative of the whole chain",
            "AUC stability does not imply calibrated evidence magnitudes",
            "this is attacker-side sensitivity analysis, not CoinScore or a privacy certificate",
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
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported weight-sensitivity artifact identity")
    measured = build_artifact(snapshot)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    measurement = artifact["measurement"]
    lines = [
        "# Global fingerprint-weight sensitivity",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "| consistency | positive mean bits | negative mean bits | AUC | shuffled AUC |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in measurement["rows"]:
        lines.append(
            f"| {row['consistency']:.2f} | {row['pos_mean']:+.6f} | "
            f"{row['neg_mean']:+.6f} | {row['auc']:.6f} | {row['shuffle_auc']:.6f} |"
        )
    lines.extend([
        "",
        f"AUC range from 0.90 through 0.99: {measurement['realistic_band_auc_range']:.6f}. "
        f"Monotone non-decreasing: {str(measurement['auc_is_monotone_non_decreasing']).lower()}.",
        "",
        "The local ranking is stable but not monotone. Evidence magnitudes remain highly "
        "sensitive to the assumed weight. Address reuse is a weak label; this is not a "
        "privacy score.",
        "",
    ])
    return "\n".join(lines)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("reproduce", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--artifact", required=True)
        command.add_argument("--markdown", required=True)
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
        if Path(args.markdown).read_text(encoding="utf-8") != render_markdown(artifact):
            raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
