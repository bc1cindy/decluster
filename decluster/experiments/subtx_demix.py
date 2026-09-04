"""Reproduce bounded de-mix diagnostics from a frozen CoinJoin-adjacent cache."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ..archive_snapshot import extract_tar_gz
from ..coinjoin_demix import coinjoin_demix
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "subtx-demix-v1"
JOINMARKET_TXID = "0cb4870cf2dfa3877851088c673d163ae3c20ebcd6505c0be964d8fbcc856bbf"


class VerificationError(ValueError):
    """The dataset or stored result violates the experiment contract."""


def _load_transactions(cache):
    transactions = []
    for path in sorted(Path(cache).glob("*.json")):
        with path.open(encoding="utf-8") as source:
            value = json.load(source)
        if isinstance(value, list) and path.name.endswith(".outspends.json"):
            continue
        if not isinstance(value, dict) or not isinstance(value.get("txid"), str):
            raise VerificationError(f"unrecognized cache object: {path}")
        transactions.append(value)
    return transactions


def _amounts(transaction):
    inputs = [entry["prevout"]["value"] for entry in transaction["vin"]]
    outputs = [entry["value"] for entry in transaction["vout"]]
    return inputs, outputs


def build_artifact(snapshot):
    with TemporaryDirectory(prefix="decluster-demix-") as temporary:
        cache = extract_tar_gz(snapshot, temporary) / ".cache"
        cache_files = len(list(cache.glob("*.json")))
        transactions = _load_transactions(cache)
    by_id = {transaction["txid"]: transaction for transaction in transactions}
    if len(by_id) != len(transactions) or JOINMARKET_TXID not in by_id:
        raise VerificationError("snapshot must contain unique txids and the declared JoinMarket round")
    inputs, outputs = _amounts(by_id[JOINMARKET_TXID])
    assignments = coinjoin_demix(inputs, outputs)
    eligible = []
    for transaction in transactions:
        try:
            tx_inputs, tx_outputs = _amounts(transaction)
        except (KeyError, TypeError):
            continue
        if 3 <= len(tx_inputs) <= 60 and len(tx_outputs) >= 2:
            eligible.append({
                "txid": transaction["txid"],
                "recovered": len(coinjoin_demix(tx_inputs, tx_outputs)),
            })
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "dataset": "subtx-demix-cache-2026-09-04-v1",
        "measurement": {
            "cache_json_files": cache_files,
            "cache_transactions": len(transactions),
            "eligible_transactions": len(eligible),
            "eligible_with_any_recovery": sum(row["recovered"] > 0 for row in eligible),
            "joinmarket": {
                "txid": JOINMARKET_TXID,
                "inputs": len(inputs),
                "outputs": len(outputs),
                "recovered_inputs": sorted(assignments),
                "recovered_changes": [assignments[index] for index in sorted(assignments)],
                "fees": [
                    max(outputs, key=outputs.count) + assignments[index] - inputs[index]
                    for index in sorted(assignments)
                ],
            },
        },
        "verdicts": {
            "joinmarket_fixture": "reproduced",
            "ordinary_transaction_specificity": "not_tested",
            "wasabi_rounds": "not_reproduced",
        },
        "limitations": [
            "the cache is CoinJoin-adjacent and has no ordinary-transaction labels",
            "22 of 25 eligible cached transactions trigger, so this population cannot support a specificity claim",
            "maker identities are inferred from an amount identity rather than independently labeled",
            "the six historical Wasabi rounds are not preserved as a dataset",
            "the fixed fee cap and most-common-output detector are local modeling choices",
            "this is attacker-side de-mix evidence, not CoinScore or a privacy certificate",
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
        raise VerificationError("unsupported subtransaction de-mix artifact identity")
    measured = build_artifact(snapshot)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    measurement = artifact["measurement"]
    joinmarket = measurement["joinmarket"]
    return "\n".join([
        "# Subtransaction de-mix diagnostic",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"The preserved JoinMarket transaction has {joinmarket['inputs']} inputs and "
        f"{joinmarket['outputs']} outputs; the amount identity recovers "
        f"{len(joinmarket['recovered_inputs'])} inputs.",
        "",
        f"The CoinJoin-adjacent cache contains {measurement['cache_transactions']} transactions. "
        f"Among {measurement['eligible_transactions']} width-eligible transactions, "
        f"{measurement['eligible_with_any_recovery']} trigger the heuristic.",
        "",
        "This cache has no ordinary-transaction labels and cannot establish specificity. "
        "The historical Wasabi result is not reproduced. This is attacker-side evidence, "
        "not a privacy score.",
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
