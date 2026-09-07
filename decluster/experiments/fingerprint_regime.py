"""Reproduce fingerprint-ranking regimes on a frozen transaction snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import fingerprint_ns
from ..fingerprint_regime import evaluate
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "fingerprint-regime-v1"
DEFAULT_DATASET = "tests/fixtures/fingerprint_blkcache_sample.json"


class VerificationError(ValueError):
    """The dataset or stored result violates this experiment's contract."""


def _load(path):
    try:
        with Path(path).open(encoding="utf-8") as source:
            transactions = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read transaction snapshot {path}: {exc}") from exc
    if not isinstance(transactions, list) or len(transactions) < 2:
        raise VerificationError("transaction snapshot must contain at least two transactions")
    txids = []
    for index, transaction in enumerate(transactions):
        if not isinstance(transaction, dict) or not isinstance(transaction.get("txid"), str):
            raise VerificationError(f"transaction {index} must be an object with a string txid")
        txids.append(transaction["txid"])
    if len(txids) != len(set(txids)):
        raise VerificationError("transaction ids must be unique")
    return transactions


def build_artifact(dataset=DEFAULT_DATASET):
    transactions = _load(dataset)
    axes = fingerprint_ns.axis_fns()
    rows = [
        evaluate(transactions, fingerprint_ns.library_weights(), "library"),
        evaluate(
            transactions,
            fingerprint_ns.measured_weights(transactions, axes),
            "snapshot_measured",
        ),
    ]
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "measurement": {"transactions": len(transactions), "rows": rows},
        "parameters": {
            "pair_draw_cap": 2000,
            "candidate_node_cap": 200,
            "seed": 0,
            "conditioning_axes": list(fingerprint_ns.CONDITIONING_AXES),
        },
        "limitations": [
            "address reuse is a weak and partly feature-dependent owner proxy",
            "candidate identities are reuse-group labels rather than wallet ownership",
            "the 600-transaction snapshot is selected and is not a chain-wide sample",
            "the snapshot-measured weights are fitted and evaluated on the same data",
            "the Lumen weighting and historical growing-cache population are not reproduced",
            "mean eccentricity is descriptive and is not an acceptance rate",
            "the result does not establish that fingerprints are universally sparse or dense",
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
        raise VerificationError("unsupported fingerprint-regime artifact identity")
    measured = build_artifact(dataset)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    measured = artifact["measurement"]
    lines = [
        "# Fingerprint ranking regime",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"Transactions: {measured['transactions']}.",
        "",
        "| weights | N-S-form AUC | F-S AUC | N-S-form top-1 | F-S top-1 | within-class mean gap |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in measured["rows"]:
        lines.append(
            f"| {row['weight_source']} | {row['ns_auc']:.6f} | {row['fs_auc']:.6f} | "
            f"{row['ns_top1']:.6f} | {row['fs_top1']:.6f} | "
            f"{row['within_class_gap_mean']:.6f} |"
        )
    lines.extend([
        "",
        "The historical claim that the conditioner interpretation is stable across weight "
        "sources does not reproduce on this fixture. Snapshot-measured weights outperform the "
        "F-S top-1 baseline and have a larger within-class mean gap, but they are fitted and "
        "evaluated on the same selected data. This is evidence of sensitivity, not evidence that "
        "fingerprints are universal sparse identifiers.",
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
    verify.add_argument("--markdown")
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
        if args.markdown is not None:
            actual = Path(args.markdown).read_text(encoding="utf-8")
            if actual != render_markdown(artifact):
                raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
