"""Measure the quantity common-input ownership asserts, inside the mapping family that admits it.

CIOH says two inputs of one transaction belong to one owner. Maurer's `p_II` says something
narrower and checkable: across every sub-transaction mapping the amounts admit, how often do two
inputs land in the same block. The two are not the same claim — a block of a value-conserving
mapping is an accounting unit, not a wallet, and a collaborative transaction can put two owners in
one block — but `p_II` bounds what the amounts alone can settle, which is the part CIOH borrows.

`p_IO` is what the link matrix usually reports and it does not cover this: it is the cross-side
quantity, and the heuristic's assertion is same-side.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from ..baselines import boltzmann
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "same-block-linkage-v1"
DEFAULT_DATASET = "data/boltzmann-fee-audit-v1.json"
MAX_COINS = 12
BALANCE_MODEL = "fee_tolerant"


class VerificationError(ValueError):
    """The dataset or stored result violates this experiment's contract."""


def _load(path):
    try:
        transactions = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read transaction snapshot {path}: {exc}") from exc
    if not isinstance(transactions, list) or not transactions:
        raise VerificationError(f"transaction snapshot must be a non-empty list: {path}")
    return transactions


def _amounts(transaction):
    inputs = [(v.get("prevout") or {}).get("value") for v in transaction.get("vin", ())]
    outputs = [o.get("value") for o in transaction.get("vout", ())]
    if any(value is None for value in inputs + outputs):
        return None
    return inputs, outputs


def _same_side(matrix, size):
    return [matrix[i][j] for i in range(size) for j in range(i + 1, size)]


def build_artifact(dataset=DEFAULT_DATASET):
    transactions = _load(dataset)
    buckets, shapes = Counter(), Counter()
    input_pairs, forced_input_pairs = 0, 0
    output_pairs, forced_output_pairs = 0, 0
    in_scope = analysed = 0
    for transaction in transactions:
        amounts = _amounts(transaction)
        if amounts is None:
            continue
        inputs, outputs = amounts
        if len(inputs) < 2 or len(inputs) + len(outputs) > MAX_COINS:
            continue
        in_scope += 1
        analysis = boltzmann.same_block_probabilities(
            inputs, outputs, max_coins=MAX_COINS, balance_model=BALANCE_MODEL,
            fee_tolerance=transaction.get("fee") or 0,
        )
        if not analysis.mapping_count:
            continue
        analysed += 1
        same_input = _same_side(analysis.input_matrix, len(inputs))
        input_pairs += len(same_input)
        forced_input_pairs += sum(1 for p in same_input if p == 1.0)
        for probability in same_input:
            buckets[f"{round(probability, 1):.1f}"] += 1
        shapes["every input pair forced" if all(p == 1.0 for p in same_input)
               else "some input pair open"] += 1
        same_output = _same_side(analysis.output_matrix, len(outputs))
        output_pairs += len(same_output)
        forced_output_pairs += sum(1 for p in same_output if p == 1.0)
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "dataset": "boltzmann-fee-audit-v1",
        "measurement": {
            "transactions": len(transactions),
            "multi_input_in_scope": in_scope,
            "with_a_feasible_mapping": analysed,
            "input_pairs": input_pairs,
            "input_pairs_forced_together": forced_input_pairs,
            "input_pairs_forced_apart": sum(count for value, count in buckets.items()
                                            if float(value) == 0.0),
            "output_pairs": output_pairs,
            "output_pairs_forced_together": forced_output_pairs,
            "p_ii_distribution": dict(sorted(buckets.items())),
            "transactions_by_shape": dict(sorted(shapes.items())),
        },
        "parameters": {
            "max_coins": MAX_COINS,
            "balance_model": BALANCE_MODEL,
            "fee_tolerance": "the transaction's own observed fee",
        },
        "limitations": [
            "a block of a value-conserving mapping is an accounting unit, not a wallet",
            "a collaborative transaction can place two owners in one block, so a forced pair is not "
            "an ownership finding",
            "only transactions with at most max_coins coins are in scope, which excludes the wide "
            "consolidations and coinjoins where the question is hardest",
            "the snapshot is 300 selected transactions and is not a chain-wide sample",
            "fee tolerance admits mappings exact conservation would refuse, which can only widen "
            "the family and lower the forced share",
            "the result is not a privacy score",
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
        raise VerificationError("unsupported same-block-linkage artifact identity")
    measured = build_artifact(dataset)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    measured = artifact["measurement"]
    share = 100.0 * measured["input_pairs_forced_together"] / measured["input_pairs"]
    lines = [
        "# What the amounts settle about co-spent inputs",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"{measured['with_a_feasible_mapping']} of {measured['multi_input_in_scope']} multi-input "
        f"transactions in scope admit a value-conserving mapping under the transaction's own fee. "
        f"Across their {measured['input_pairs']} input pairs, Maurer's `p_II` says how often the "
        "two coins share a block in every mapping the amounts admit.",
        "",
        "| p_II | input pairs |",
        "|---:|---:|",
    ]
    for value, count in measured["p_ii_distribution"].items():
        lines.append(f"| {value} | {count} |")
    lines += [
        "",
        f"**{measured['input_pairs_forced_together']} of {measured['input_pairs']} pairs "
        f"({share:.1f}%) are forced together** — no admissible mapping separates them — and "
        f"{measured['input_pairs_forced_apart']} are forced apart. The amounts corroborate the "
        "co-spend far more often than they contest it here, and on this snapshot they never "
        "contest it outright.",
        "",
        f"On the output side, {measured['output_pairs_forced_together']} of "
        f"{measured['output_pairs']} pairs are forced together.",
        "",
        "**This is not an ownership result, and the gap is the point.** A block of a "
        "value-conserving mapping is an accounting unit; a collaborative transaction can put two "
        "owners in one block and satisfy every constraint measured here. What the number bounds is "
        "what the amounts alone can settle — the part common-input ownership borrows without "
        "checking.",
        "",
        f"Scope is capped at {artifact['parameters']['max_coins']} coins, which excludes the wide "
        "consolidations and coinjoins where the question is hardest, and the fee-tolerant model "
        "admits mappings exact conservation would refuse — which can only widen the family and "
        "lower the forced share. The snapshot is 300 selected transactions and is not chain-wide.",
        "",
    ]
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
