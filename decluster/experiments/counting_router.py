"""Measure the current radix-to-sparse counting router on the amount snapshot."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from ..counting import KNEE, count_w, guaranteed_log_w, radix_applies
from ..measure import load_ndjson
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "counting-router-v1"
DATASET = "data/amount-channel-812695-812831-v1.json"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _transactions(dataset):
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
    import dss

    routes = Counter()
    transactions = 0
    guaranteed = 0
    radix_precondition = 0
    raw_radix_positive = 0
    raw_radix_positive_without_precondition = 0
    for transaction in _transactions(dataset):
        transactions += 1
        inputs = [item["prevout"]["value"] for item in transaction["vin"]]
        outputs = [item["value"] for item in transaction["vout"]]
        applies = radix_applies(outputs)
        radix_precondition += applies
        raw_radix = dss.radix_mappings(outputs, KNEE)
        raw_positive = (raw_radix.get("count") or 0) > 0 or raw_radix.get("log_w") is not None
        raw_radix_positive += raw_positive
        raw_radix_positive_without_precondition += raw_positive and not applies

        result = count_w(inputs, outputs)
        routes[(result["method"], result["kind"])] += 1
        guaranteed += guaranteed_log_w(result) is not None

    return {
        "population": {"multi_input_transactions": transactions},
        "current_router": {
            "by_method_and_kind": {
                f"{method}:{kind}": count
                for (method, kind), count in sorted(routes.items())
            },
            "guaranteed_nonzero_log_w": guaranteed,
        },
        "radix_precondition_audit": {
            "precondition_applies": radix_precondition,
            "raw_positive": raw_radix_positive,
            "raw_positive_without_precondition": raw_radix_positive_without_precondition,
        },
    }


def build_artifact(dataset=DATASET):
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "corpus": "public Bitcoin transaction snapshot",
        "parameters": {"knee": KNEE, "route": ["radix", "sparse", "none"]},
        "report": build_report(dataset),
        "limitations": [
            "W(E) is a transaction-level subset-sum diagnostic, not a mapping count",
            "raw radix output is audited only to test its required precondition",
            "zero-count and unknown outcomes provide no ambiguity evidence",
            "Sasamoto remains an explicit estimator and is not a router tier",
            "timings and synthetic L-estimator comparisons are outside this run",
            "this diagnostic is not a privacy score or CoinScore",
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
        raise VerificationError("unsupported counting-router artifact identity")
    measured = build_artifact(dataset)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    report = artifact["report"]
    population = report["population"]
    router = report["current_router"]
    radix = report["radix_precondition_audit"]
    routes = router["by_method_and_kind"]
    return "\n".join([
        "# Counting-router observations",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"The current router evaluates {population['multi_input_transactions']:,} transactions. "
        f"It resolves {router['guaranteed_nonzero_log_w']:,}: "
        f"{routes.get('radix:exact', 0):,} radix exact, "
        f"{routes.get('sparse:exact', 0):,} sparse exact, and "
        f"{routes.get('sparse:lower_bound', 0):,} sparse lower bound. "
        f"The remaining {routes.get('none:unknown', 0):,} are unknown.",
        "",
        f"The radix precondition applies to {radix['precondition_applies']:,} transactions. "
        f"Calling radix without that gate returns a positive reading {radix['raw_positive']:,} "
        f"times, including {radix['raw_positive_without_precondition']:,} outside its precondition.",
        "",
        "Sasamoto is not a router tier. These counts are not mapping entropy or CoinScore.",
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
