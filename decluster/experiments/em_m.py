"""Reproduce the per-axis Fellegi-Sunter EM diagnostic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ..archive_snapshot import extract_tar_gz
from ..em_m_comparison import evaluate
from ..fingerprint_validate import load_blkcache
from ..reproducibility import fingerprint_source
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "em-m-v1"
DATASET_ID = "fs-blkcache-2026-09-04-v1"


class VerificationError(ValueError):
    """The stored result differs from a fresh execution."""


def build_artifact(snapshot):
    with TemporaryDirectory(prefix="decluster-em-m-") as temporary:
        root = extract_tar_gz(snapshot, temporary)
        cache = root / ".blkcache"
        transactions = load_blkcache(str(cache))
        measurement = evaluate(transactions)
        source = fingerprint_source(str(cache / "*.json"))
        source.update(pattern=".blkcache/*.json", transactions=len(transactions))
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "dataset": DATASET_ID,
        "parameters": {"pair_cap_per_class": 4000, "seed": 0, "fixed_u": True},
        "source": source,
        "measurement": measurement,
        "historical_comparison": {
            "status": "not_reproduced",
            "reason": "the preserved 22,112-transaction snapshot is not the historical 165,832-transaction cache",
        },
        "limitations": [
            "address reuse is a weak and partly feature-dependent ownership proxy",
            "the balanced selected sample does not represent population prevalence",
            "EM is fitted and evaluated on the same pair sample",
            "the model assumes conditional independence between correlated axes",
            "u is fixed at the measured collision rate",
            "the small AUC difference is measured without a pre-registered separability verdict",
            "this is attacker-side parameter diagnosis, not CoinScore or a privacy certificate",
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
        raise VerificationError("unsupported EM-m artifact identity")
    measured = build_artifact(snapshot)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    measurement = artifact["measurement"]
    aucs = measurement["library_scorer_auc"]
    return "\n".join([
        "# Per-axis Fellegi–Sunter EM diagnostic",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"Transactions: {measurement['transactions']}; EM iterations: "
        f"{measurement['fit']['iterations']}; inferred selected-pair fraction: "
        f"{measurement['fit']['inferred_pair_fraction']:.6f}.",
        "",
        "| parameter source | LibraryScorer AUC |",
        "|---|---:|",
        f"| fixed 0.95 | {aucs['fixed_0_95']:.6f} |",
        f"| unsupervised EM | {aucs['em']:.6f} |",
        f"| address-reuse agreement | {aucs['address_reuse_agreement']:.6f} |",
        "",
        f"EM minus fixed AUC: {measurement['em_minus_fixed_auc']:+.6f}. This difference is "
        "descriptive; no pre-registered separability verdict was run.",
        "",
        "The historical 165,832-transaction table is not reproduced by the preserved "
        "22,112-transaction snapshot. Address reuse is a weak label, and this is an "
        "attacker-side parameter diagnostic rather than a privacy score.",
        "",
    ])


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
