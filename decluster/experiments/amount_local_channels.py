"""Measure local refuse-only amount channels without DSS or mapping enumeration."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from ..coinjoin_demix import coinjoin_demix
from ..conservation import forced_in_round
from ..extractors import x_uih
from ..measure import load_ndjson
from ..monitor import is_coinjoin
from ..result_artifacts import canonical_json_bytes, write_canonical_json
from ..subtransaction import subtransactions

EXPERIMENT_ID = "amount-local-channels-v1"
DATASET = "data/amount-channel-812695-812831-v1.json"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _complete(transaction):
    inputs = transaction.get("vin") or []
    outputs = transaction.get("vout") or []
    return (
        bool(inputs)
        and all((item.get("prevout") or {}).get("value") is not None for item in inputs)
        and all(item.get("value") is not None for item in outputs)
    )


def _demixes(transaction):
    inputs = [item["prevout"]["value"] for item in transaction["vin"]]
    outputs = [item["value"] for item in transaction.get("vout") or []]
    assignment = coinjoin_demix(inputs, outputs)
    return len(set(assignment.values())) >= 2


def build_report(dataset=DATASET):
    transactions = [transaction for transaction, _height in load_ndjson(dataset)]
    usable = [transaction for transaction in transactions if _complete(transaction)]
    multi = [transaction for transaction in usable if len(transaction["vin"]) >= 2]

    shape = sum(is_coinjoin(transaction) for transaction in multi)
    demixed = sum(_demixes(transaction) for transaction in multi)
    uih = Counter(x_uih(transaction) for transaction in multi)

    two_by_two = [
        transaction
        for transaction in usable
        if len(transaction["vin"]) == 2 and len(transaction.get("vout") or []) == 2
    ]
    ranked = 0
    tied = 0
    for transaction in two_by_two:
        readings, _bits = subtransactions(transaction)
        if not readings:
            continue
        ranked += 1
        tied += len(readings) > 1 and readings[0][1] == readings[1][1]

    forced = 0
    for transaction in multi:
        largest_input = max(
            item["prevout"]["value"] for item in transaction["vin"]
        )
        forced += bool(forced_in_round(transaction, largest_input))

    return {
        "population": {
            "transactions": len(transactions),
            "complete_amounts": len(usable),
            "multi_input": len(multi),
            "two_input_two_output": len(two_by_two),
        },
        "coinjoin": {"shape_detected": shape, "demixed": demixed},
        "unnecessary_input": {
            "fires": len(multi) - uih.get("none", 0),
            "classes": dict(sorted(uih.items())),
        },
        "subtransaction_roundness": {"ranked": ranked, "top_tied": tied},
        "conservation": {
            "known_participant": "largest input value",
            "forced_output_value": forced,
        },
    }


def build_artifact(dataset=DATASET):
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "corpus": "public Bitcoin transaction snapshot",
        "report": build_report(dataset),
        "limitations": [
            "the snapshot covers one 137-block interval from 2023",
            "no recognized JoinMarket round appears in the measured population",
            "roundness ties show abstention, not ownership truth",
            "the conservation probe assumes the largest input is the known participant",
            "this run excludes subset-sum, DSS, mapping entropy, and score composition",
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


def verify_artifact(artifact, *, dataset=DATASET):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported local amount-channel artifact identity")
    measured = build_artifact(dataset)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    report = artifact["report"]
    population = report["population"]
    return "\n".join([
        "# Local amount-channel observations",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"The snapshot contains {population['transactions']:,} transactions and "
        f"{population['multi_input']:,} complete multi-input transactions.",
        "",
        f"CoinJoin shape fires {report['coinjoin']['shape_detected']:,} times; de-mix "
        f"resolves {report['coinjoin']['demixed']:,}. Unnecessary-input fires "
        f"{report['unnecessary_input']['fires']:,} times.",
        "",
        f"The 2×2 roundness model ranks {report['subtransaction_roundness']['ranked']:,} "
        f"transactions and ties at the top for "
        f"{report['subtransaction_roundness']['top_tied']:,}.",
        "",
        "This run excludes subset-sum, DSS, mapping entropy, and score composition.",
        "",
    ])


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DATASET)
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
        artifact = verify_artifact(load_artifact(args.artifact), dataset=args.dataset)
        if args.markdown is not None:
            actual = Path(args.markdown).read_text(encoding="utf-8")
            if actual != render_markdown(artifact):
                raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
