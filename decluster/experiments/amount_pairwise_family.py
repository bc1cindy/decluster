"""Measure DSS pairwise rows on the Bitcoin amount-channel snapshot."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import multiprocessing
from pathlib import Path
from queue import Empty

from .amount_mapping_family import DATASET, _transactions
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "amount-pairwise-family-v1"
DEFAULT_CAP = 300
DEFAULT_WALL_SECONDS = 3.0


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _worker(inputs, outputs, queue):
    try:
        import dss

        queue.put(("answered", dss.pairwise_link_prob(inputs, outputs, None)))
    except BaseException as exc:
        queue.put(("failed", f"{type(exc).__name__}: {exc}"))


def _bounded_matrix(inputs, outputs, wall_seconds):
    context = multiprocessing.get_context("spawn")
    queue = context.Queue(maxsize=1)
    process = context.Process(target=_worker, args=(inputs, outputs, queue))
    process.start()
    process.join(wall_seconds)
    if process.is_alive():
        process.terminate()
        process.join()
        queue.close()
        return "timed_out", None
    try:
        status, result = queue.get(timeout=1.0)
    except Empty:
        status, result = "failed", None
    finally:
        queue.close()
    if status == "answered" and result is None:
        return "refused", None
    if status == "answered" and not isinstance(result, list):
        return "failed", None
    return status, result


def build_report(dataset=DATASET, cap=DEFAULT_CAP, wall_seconds=DEFAULT_WALL_SECONDS):
    outcomes = Counter()
    selected_transactions = 0
    selected_input_rows = 0
    selected_outputs = 0
    returned_rows = 0
    nonempty_rows = 0
    singleton_support_rows = 0
    full_support_rows = 0

    for transaction in _transactions(dataset, cap):
        selected_transactions += 1
        inputs = [item["prevout"]["value"] for item in transaction["vin"]]
        outputs = [item["value"] for item in transaction["vout"]]
        selected_input_rows += len(inputs)
        selected_outputs += len(outputs)
        status, matrix = _bounded_matrix(inputs, outputs, wall_seconds)
        outcomes[status] += 1
        if status != "answered":
            continue
        if len(matrix) != len(inputs) or any(len(row) != len(outputs) for row in matrix):
            outcomes["answered"] -= 1
            outcomes["failed"] += 1
            continue
        returned_rows += len(matrix)
        for row in matrix:
            support = sum(probability > 0.0 for probability in row)
            nonempty_rows += support > 0
            singleton_support_rows += support == 1
            full_support_rows += support == len(outputs) and bool(outputs)

    return {
        "population": {
            "selected_transactions": selected_transactions,
            "selected_input_rows": selected_input_rows,
            "selected_outputs": selected_outputs,
            "selection": "first complete multi-input transactions in source order",
        },
        "outcomes": {
            "answered": outcomes["answered"],
            "refused": outcomes["refused"],
            "timed_out": outcomes["timed_out"],
            "failed": outcomes["failed"],
        },
        "restricted_family_rows": {
            "returned": returned_rows,
            "nonempty_support": nonempty_rows,
            "singleton_support": singleton_support_rows,
            "full_output_support": full_support_rows,
        },
    }


def build_artifact(dataset=DATASET, cap=DEFAULT_CAP, wall_seconds=DEFAULT_WALL_SECONDS):
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "corpus": "public Bitcoin transaction snapshot",
        "parameters": {"cap": cap, "wall_seconds_per_transaction": wall_seconds},
        "report": build_report(dataset, cap, wall_seconds),
        "limitations": [
            "the matrix is a uniform marginal over DSS's restricted mapping family",
            "a singleton-support row is not a globally deterministic ownership link",
            "the exact-oracle audit found false certainties outside the restricted family",
            "refusal, timeout, and execution failure are distinct outcomes",
            "wall-time outcomes are resource- and platform-dependent",
            "the sample is the first complete multi-input transactions in one 137-block snapshot",
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


def verify_artifact(artifact, *, dataset=DATASET, cap=DEFAULT_CAP,
                    wall_seconds=DEFAULT_WALL_SECONDS):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported pairwise-family artifact identity")
    measured = build_artifact(dataset, cap, wall_seconds)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    report = artifact["report"]
    population = report["population"]
    outcomes = report["outcomes"]
    rows = report["restricted_family_rows"]
    return "\n".join([
        "# DSS pairwise restricted-family diagnostic",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"The run selects {population['selected_transactions']:,} transactions containing "
        f"{population['selected_input_rows']:,} input rows. {outcomes['answered']:,} transactions "
        f"answer, {outcomes['refused']:,} refuse, {outcomes['timed_out']:,} time out, and "
        f"{outcomes['failed']:,} fail.",
        "",
        f"The answered matrices return {rows['returned']:,} rows, of which "
        f"{rows['nonempty_support']:,} have nonempty support and "
        f"{rows['singleton_support']:,} have singleton support.",
        "",
        "Singleton support means only that every mapping in DSS's restricted family selects the "
        "same output. It is not a globally deterministic ownership link.",
        "",
    ])


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DATASET)
    parser.add_argument("--cap", type=int, default=DEFAULT_CAP)
    parser.add_argument("--wall-seconds", type=float, default=DEFAULT_WALL_SECONDS)
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
    if args.cap <= 0 or args.wall_seconds <= 0:
        raise SystemExit("--cap and --wall-seconds must be positive")
    if args.command == "reproduce":
        artifact = build_artifact(args.dataset, args.cap, args.wall_seconds)
        write_canonical_json(args.artifact, artifact)
        destination = Path(args.markdown)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_markdown(artifact), encoding="utf-8")
    else:
        artifact = verify_artifact(
            load_artifact(args.artifact), dataset=args.dataset,
            cap=args.cap, wall_seconds=args.wall_seconds,
        )
        if args.markdown is not None:
            actual = Path(args.markdown).read_text(encoding="utf-8")
            if actual != render_markdown(artifact):
                raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
