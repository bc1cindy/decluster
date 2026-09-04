"""Reproduce the pair-level Bayesian versus Fellegi-Sunter comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ..archive_snapshot import extract_tar_gz
from ..bayes_fs_comparison import evaluate
from ..fingerprint_validate import load_blkcache
from ..reproducibility import fingerprint_source
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "bayes-vs-fs-v1"
DATASET_ID = "fs-blkcache-2026-09-04-v1"


class VerificationError(ValueError):
    """The stored result differs from a fresh execution."""


def build_artifact(snapshot, *, pair_cap=4000, seed=0, n_samples=2000, burn=500):
    with TemporaryDirectory(prefix="decluster-bayes-fs-") as temporary:
        root = extract_tar_gz(snapshot, temporary)
        cache = root / ".blkcache"
        transactions = load_blkcache(str(cache))
        measurement = evaluate(
            transactions,
            pair_cap=pair_cap,
            seed=seed,
            n_samples=n_samples,
            burn=burn,
        )
        source = fingerprint_source(str(cache / "*.json"))
        source.update(pattern=".blkcache/*.json", transactions=len(transactions))
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "dataset": DATASET_ID,
        "parameters": {
            "pair_cap_per_class": pair_cap,
            "seed": seed,
            "gibbs_samples": n_samples,
            "gibbs_burn": burn,
            "beta_prior": [8.5, 1.5],
        },
        "source": source,
        "measurement": measurement,
        "historical_comparison": {
            "status": "not_reproduced",
            "reason": "the preserved snapshot produces materially different metrics from the historical Markdown",
        },
        "limitations": [
            "address reuse is a weak and partly feature-dependent ownership proxy",
            "the balanced positive-negative sample does not represent population prevalence",
            "parameters are fitted and evaluated on the same selected pair sample",
            "the model assumes conditional independence between correlated axes",
            "u is fixed at the measured collision rate",
            "cluster intervals propagate pair probabilities independently and are not a joint partition posterior",
            "borderline nodes are purpose-selected and neither cluster diagnostic is chain-wide",
            "this is attacker-side record-linkage evidence, not CoinScore or a privacy certificate",
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
        raise VerificationError("unsupported Bayes-versus-FS artifact identity")
    measured = build_artifact(snapshot)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    measurement = artifact["measurement"]
    lines = [
        "# Pair-level Bayesian and Fellegi–Sunter comparison",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"Transactions: {measurement['transactions']}; positive pairs: "
        f"{measurement['pairs']['positive']}; negative pairs: {measurement['pairs']['negative']}.",
        "",
        "| scorer | AUC | ECE |",
        "|---|---:|---:|",
    ]
    for row in measurement["discrimination"]:
        lines.append(f"| {row['scorer']} | {row['auc']:.6f} | {row['ece']:.6f} |")
    lines.extend([
        "",
        "The preserved snapshot does not reproduce the metrics in the former handwritten report. "
        "These values are the canonical rerun. Address reuse is a weak label, calibration is on a "
        "balanced selected sample, and the cluster bands are independent-edge diagnostics rather "
        "than a posterior over ownership partitions.",
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
