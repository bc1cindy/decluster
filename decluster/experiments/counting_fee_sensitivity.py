"""Measure how the counting interfaces react to fees on a fixed transaction shape."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..counting import count_w, per_coin_log_w, w_total
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "counting-fee-sensitivity-v1"
INPUTS = (400_000, 300_000, 300_000)
OUTPUT_TOTAL = 1_000_000
FEES = (0, 1, 10, 100, 1_000, 4_956)


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def build_artifact():
    observations = []
    for fee in FEES:
        outputs = (600_000, 400_000 - fee)
        cascade = w_total(INPUTS, outputs)
        router = count_w(INPUTS, outputs)
        per_coin = per_coin_log_w(INPUTS, outputs)
        observations.append({
            "fee_sat": fee,
            "outputs_sat": list(outputs),
            "cascade": cascade,
            "router": router,
            "measured_input_indices": sorted(per_coin),
            "per_coin_log_w": {str(index): per_coin[index] for index in sorted(per_coin)},
        })
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "fixture": {"inputs_sat": list(INPUTS), "output_total_before_fee_sat": OUTPUT_TOTAL},
        "observations": observations,
        "limitations": [
            "this is a deterministic sensitivity fixture, not a population estimate",
            "the transaction-level subset-sum count and fee-aware per-coin count are "
            "different objects",
            "an absent per-coin index is a refusal to measure, not zero ambiguity",
            "these diagnostics are not mapping entropy, a privacy score, or CoinScore",
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
        raise VerificationError("unsupported counting-fee-sensitivity artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    rows = [
        "# Counting fee sensitivity",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "| fee (sat) | transaction count | per-coin inputs measured |",
        "|---:|---:|---:|",
    ]
    for observation in artifact["observations"]:
        rows.append(
            f"| {observation['fee_sat']:,} | {observation['router']['count']} | "
            f"{len(observation['measured_input_indices'])} |"
        )
    rows.extend([
        "",
        "The transaction-level result remains defined after the per-coin interface stops measuring "
        "any input. The two interfaces therefore must not be substituted for one another.",
        "",
        "This fixture is a mechanism check, not a population estimate or privacy score.",
        "",
    ])
    return "\n".join(rows)


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
