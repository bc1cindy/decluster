"""Measure the DSS per-coin amount diagnostic and its transaction-level gate."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
from statistics import median

from ..cost import _reachable, amount_cuts, dss_oracle
from ..counting import count_w, guaranteed_log_w
from ..measure import load_ndjson
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "amount-per-coin-v1"
DATASET = "data/amount-channel-812695-812831-v1.json"
CUT_THRESHOLD = 1.0


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


def _role(coin):
    role = coin.get("role")
    if role == "in":
        return "input"
    if role == "out":
        return "output"
    raise ValueError(f"unsupported DSS coin role: {role!r}")


def build_report(dataset=DATASET, cut_threshold=CUT_THRESHOLD):
    population = Counter()
    reachable = Counter()
    raw_candidates = Counter()
    gated_candidates = Counter()
    exact_gate_candidates = Counter()
    finite_log_w = []
    raw_candidate_transactions = 0
    gated_candidate_transactions = 0
    gate_resolved_transactions = 0

    for transaction in _transactions(dataset):
        inputs = [item["prevout"]["value"] for item in transaction["vin"]]
        outputs = [item["value"] for item in transaction["vout"]]
        population["transactions"] += 1
        population["input"] += len(inputs)
        population["output"] += len(outputs)

        per_coin = dss_oracle(inputs, outputs)
        raw_here = False
        for coin in per_coin["coins"]:
            role = _role(coin)
            log_w = coin.get("log_w")
            if not _reachable(log_w):
                continue
            reachable[role] += 1
            finite_log_w.append(log_w)
            if log_w <= cut_threshold:
                raw_candidates[role] += 1
                raw_here = True
        raw_candidate_transactions += raw_here

        whole = count_w(inputs, outputs)
        if guaranteed_log_w(whole) is None:
            continue
        gate_resolved_transactions += 1
        candidates = amount_cuts(
            inputs,
            outputs,
            lambda _inputs, _outputs, report=per_coin: report,
            cut_threshold=cut_threshold,
            count_oracle=lambda _inputs, _outputs, result=whole: result,
        )
        gated_candidate_transactions += bool(candidates)
        for candidate in candidates:
            role = _role({"role": candidate.role})
            gated_candidates[role] += 1
            if candidate.transaction_count_exact:
                exact_gate_candidates[role] += 1

    total_coins = population["input"] + population["output"]
    finite = len(finite_log_w)
    return {
        "population": {
            "transactions": population["transactions"],
            "inputs": population["input"],
            "outputs": population["output"],
            "coins": total_coins,
        },
        "per_coin_density": {
            "reachable": {
                "input": reachable["input"],
                "output": reachable["output"],
                "total": finite,
            },
            "unreachable": total_coins - finite,
            "finite_log_w": {
                "minimum": min(finite_log_w) if finite_log_w else None,
                "median": median(finite_log_w) if finite_log_w else None,
                "maximum": max(finite_log_w) if finite_log_w else None,
            },
        },
        "ungated_diagnostic": {
            "candidate_transactions": raw_candidate_transactions,
            "candidates": {
                "input": raw_candidates["input"],
                "output": raw_candidates["output"],
                "total": sum(raw_candidates.values()),
            },
        },
        "transaction_gated": {
            "resolved_transactions": gate_resolved_transactions,
            "candidate_transactions": gated_candidate_transactions,
            "candidates": {
                "input": gated_candidates["input"],
                "output": gated_candidates["output"],
                "total": sum(gated_candidates.values()),
            },
            "candidates_with_exact_transaction_count": {
                "input": exact_gate_candidates["input"],
                "output": exact_gate_candidates["output"],
                "total": sum(exact_gate_candidates.values()),
            },
        },
    }


def build_artifact(dataset=DATASET, cut_threshold=CUT_THRESHOLD):
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "corpus": "public Bitcoin transaction snapshot",
        "parameters": {"cut_threshold_natural_log": cut_threshold},
        "report": build_report(dataset, cut_threshold),
        "limitations": [
            "DSS per-coin log_w is a knee-truncated diagnostic, not an exact mapping count",
            "unreachable coins are missing measurements and are never candidates",
            "the transaction gate and per-coin diagnostic measure different objects",
            "an exact transaction count does not make a per-coin candidate exact",
            "input and output indices have separate identities",
            "candidates are refuse signals, not ownership proofs or privacy scores",
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


def verify_artifact(artifact, *, dataset=DATASET, cut_threshold=CUT_THRESHOLD):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported per-coin amount artifact identity")
    measured = build_artifact(dataset, cut_threshold)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    report = artifact["report"]
    population = report["population"]
    density = report["per_coin_density"]
    raw = report["ungated_diagnostic"]
    gated = report["transaction_gated"]
    return "\n".join([
        "# DSS per-coin amount diagnostic",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"The run evaluates {population['coins']:,} coins in "
        f"{population['transactions']:,} complete multi-input transactions. DSS returns a "
        f"finite per-coin reading for {density['reachable']['total']:,} coins and no reading for "
        f"{density['unreachable']:,}.",
        "",
        f"Before the transaction gate, {raw['candidates']['total']:,} candidates occur in "
        f"{raw['candidate_transactions']:,} transactions: {raw['candidates']['input']:,} inputs "
        f"and {raw['candidates']['output']:,} outputs.",
        "",
        f"After requiring a conservative nonzero transaction-level W(E), "
        f"{gated['candidates']['total']:,} candidates remain in "
        f"{gated['candidate_transactions']:,} transactions. An exact transaction count records "
        "the gate's provenance; it does not make the per-coin reading exact.",
        "",
        "These are refuse-only diagnostics, not ownership proofs, privacy scores, or CoinScore.",
        "",
    ])


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DATASET)
    parser.add_argument("--cut-threshold", type=float, default=CUT_THRESHOLD)
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
    if not math.isfinite(args.cut_threshold):
        raise SystemExit("--cut-threshold must be finite")
    if args.command == "reproduce":
        artifact = build_artifact(args.dataset, args.cut_threshold)
        write_canonical_json(args.artifact, artifact)
        destination = Path(args.markdown)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_markdown(artifact), encoding="utf-8")
    else:
        artifact = verify_artifact(
            load_artifact(args.artifact),
            dataset=args.dataset,
            cut_threshold=args.cut_threshold,
        )
        if args.markdown is not None:
            actual = Path(args.markdown).read_text(encoding="utf-8")
            if actual != render_markdown(artifact):
                raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
