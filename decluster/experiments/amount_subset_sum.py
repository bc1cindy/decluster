"""Measure transaction-level subset-sum W(E) on the amount-channel snapshot."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from ..counting import MAX_INPUTS, guaranteed_log_w, w_total
from ..measure import load_ndjson
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "amount-subset-sum-v1"
DATASET = "data/amount-channel-812695-812831-v1.json"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _multi_input_transactions(dataset):
    for transaction, _height in load_ndjson(dataset):
        inputs = transaction.get("vin") or []
        outputs = transaction.get("vout") or []
        if (
            len(inputs) >= 2
            and all((item.get("prevout") or {}).get("value") is not None for item in inputs)
            and all(item.get("value") is not None for item in outputs)
        ):
            yield transaction


def build_report(dataset=DATASET):
    kinds = Counter()
    guaranteed = 0
    exact_zero = 0
    transactions = 0
    for transaction in _multi_input_transactions(dataset):
        inputs = [item["prevout"]["value"] for item in transaction["vin"]]
        outputs = [item["value"] for item in transaction["vout"]]
        result = w_total(inputs, outputs)
        kind = str(result.get("kind", "unknown")).lower()
        kinds[kind] += 1
        guaranteed += guaranteed_log_w(result) is not None
        exact_zero += kind == "exact" and (result.get("count") or 0) == 0
        transactions += 1
    return {
        "population": {"multi_input": transactions, "maximum_inputs": MAX_INPUTS},
        "outcomes": {
            "by_kind": dict(sorted(kinds.items())),
            "guaranteed_nonzero_log_w": guaranteed,
            "exact_zero": exact_zero,
        },
    }


def build_artifact(dataset=DATASET):
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "corpus": "public Bitcoin transaction snapshot",
        "report": build_report(dataset),
        "limitations": [
            "W(E) is a per-target subset count, not a Maurer mapping count",
            "the whole-transaction count is fee-blind",
            "exact zero means no exact subset hit and supplies no ambiguity evidence",
            "transactions above sixteen inputs are reported as unknown",
            "only exact and lower-bound tiers can support a conservative lower bound",
            "this run does not compute pairwise links, entropy, or CoinScore",
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
        raise VerificationError("unsupported amount subset-sum artifact identity")
    measured = build_artifact(dataset)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    report = artifact["report"]
    population = report["population"]
    outcomes = report["outcomes"]
    return "\n".join([
        "# Transaction-level subset-sum W(E)",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"Of {population['multi_input']:,} multi-input transactions, "
        f"{outcomes['by_kind'].get('exact', 0):,} return `exact` and "
        f"{outcomes['by_kind'].get('unknown', 0):,} return `unknown`.",
        "",
        f"Among the exact results, {outcomes['exact_zero']:,} find no exact subset hit. "
        f"Only {outcomes['guaranteed_nonzero_log_w']:,} results expose a usable "
        "nonzero conservative log W.",
        "",
        "W(E) is not a mapping count, pairwise-link oracle, entropy, or CoinScore.",
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
