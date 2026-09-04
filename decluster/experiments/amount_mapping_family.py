"""Measure entropy and certain links inside DSS's restricted mapping family."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import multiprocessing
from pathlib import Path
from queue import Empty

from ..measure import load_ndjson
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "amount-mapping-family-v1"
DATASET = "data/amount-channel-812695-812831-v1.json"
DEFAULT_CAP = 250
DEFAULT_WALL_SECONDS = 3.0


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _worker(inputs, outputs, queue):
    try:
        import dss

        queue.put(("answered", dss.mapping_analysis(inputs, outputs, None)))
    except BaseException as exc:
        queue.put(("failed", f"{type(exc).__name__}: {exc}"))


def _bounded_analysis(inputs, outputs, wall_seconds):
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
    if status == "answered" and (
        result is None or (isinstance(result, dict) and result.get("status") == "refused")
    ):
        return "refused", None
    if status == "answered" and (
        not isinstance(result, dict) or result.get("status") != "complete"
    ):
        return "failed", None
    return status, result


def _transactions(dataset, cap):
    selected = 0
    for transaction, _height in load_ndjson(dataset):
        inputs = transaction.get("vin") or []
        outputs = transaction.get("vout") or []
        if (
            len(inputs) >= 2
            and all((item.get("prevout") or {}).get("value") is not None for item in inputs)
            and all(item.get("value") is not None for item in outputs)
        ):
            yield transaction
            selected += 1
            if selected == cap:
                return


def build_report(dataset=DATASET, cap=DEFAULT_CAP, wall_seconds=DEFAULT_WALL_SECONDS):
    outcomes = Counter()
    entropy = Counter()
    mappings = 0
    certain_links = 0
    selected = 0
    for transaction in _transactions(dataset, cap):
        selected += 1
        inputs = [item["prevout"]["value"] for item in transaction["vin"]]
        outputs = [item["value"] for item in transaction["vout"]]
        status, analysis = _bounded_analysis(inputs, outputs, wall_seconds)
        outcomes[status] += 1
        if status != "answered":
            continue
        value = analysis["entropy"]
        if value == 0.0:
            entropy["zero"] += 1
        elif value <= 4.0:
            entropy["above_zero_to_four"] += 1
        else:
            entropy["above_four"] += 1
        mappings += analysis["n_non_derived"]
        certain_links += len(analysis["deterministic_links"])
    return {
        "population": {
            "selected_transactions": selected,
            "selection": "first complete multi-input transactions in source order",
        },
        "outcomes": {
            "answered": outcomes["answered"],
            "refused": outcomes["refused"],
            "timed_out": outcomes["timed_out"],
            "failed": outcomes["failed"],
        },
        "restricted_family": {
            "entropy_bins_bits": {
                "zero": entropy["zero"],
                "above_zero_to_four": entropy["above_zero_to_four"],
                "above_four": entropy["above_four"],
            },
            "non_derived_mappings": mappings,
            "certain_input_output_links": certain_links,
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
            "DSS enumerates a strict sub-family of the full balanced mappings",
            "entropy is uniform over that restricted family, not a posterior over ownership",
            "certain links are certain only within the restricted family",
            "refusal, timeout, and execution failure are distinct outcomes",
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
        raise VerificationError("unsupported mapping-family artifact identity")
    measured = build_artifact(dataset, cap, wall_seconds)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    report = artifact["report"]
    outcomes = report["outcomes"]
    family = report["restricted_family"]
    bins = family["entropy_bins_bits"]
    return "\n".join([
        "# DSS restricted mapping-family diagnostic",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"Of {report['population']['selected_transactions']:,} selected transactions, "
        f"{outcomes['answered']:,} answer, {outcomes['refused']:,} refuse, "
        f"{outcomes['timed_out']:,} time out, and {outcomes['failed']:,} fail.",
        "",
        f"Within the answered restricted families, {bins['zero']:,} have zero-bit entropy, "
        f"{bins['above_zero_to_four']:,} have more than zero and at most four bits, and "
        f"{bins['above_four']:,} have more than four bits. The families contain "
        f"{family['non_derived_mappings']:,} non-derived mappings and "
        f"{family['certain_input_output_links']:,} input-output links shared by every mapping.",
        "",
        "Certainty and entropy apply only to DSS's restricted family, not to the full mapping "
        "space or an ownership posterior.",
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
