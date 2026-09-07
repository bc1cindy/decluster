"""Measure the fingerprint library's per-axis bits on the one population that is still here.

Every weight in `library.py` is minus the log-share of a value, and the docstring says where the
shares came from: a ~105k uniform whole-chain BigQuery sample. That export no longer exists, so the
shipped table cannot be re-derived, and the numbers it feeds — every evidence magnitude the scorer
reports — rest on a calibration a reader cannot check.

This does not restore that provenance and does not claim to. It measures the same quantity on the
committed block cache and reports the distance, per value, so the size of the unverifiable part is
on the record rather than assumed small. The two populations differ by construction — 22k
block-sampled transactions against 105k uniform ones — so a divergence is expected; what was not
on the record is how large it is.

A value the cache never shows cannot be calibrated from it at all, and those are counted rather
than filled in.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from .. import engine, extractors, library
from ..archive_snapshot import extract_tar_gz
from ..fingerprint_validate import load_blkcache
from ..reproducibility import fingerprint_source
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "library-calibration-v1"


class VerificationError(ValueError):
    """The dataset or stored result violates this experiment's contract."""


def _extractor(name):
    function = getattr(extractors, name, None) or getattr(engine, name, None)
    if function is None:
        raise VerificationError(f"library names an extractor that does not exist: {name}")
    return function


def _observed(transactions, function):
    counts = Counter()
    for transaction in transactions:
        try:
            value = function(transaction)
        except Exception:                       # a partial record, not a bug in the axis
            counts["__unreadable__"] += 1
            continue
        counts[value] += 1
    scored = {value: count for value, count in counts.items()
              if value not in ("__unreadable__", extractors.NA)}
    return scored, counts["__unreadable__"], counts.get(extractors.NA, 0)


def _axis(entry, transactions):
    scored, unreadable, abstained = _observed(transactions, _extractor(entry["extractor"]))
    total = sum(scored.values())
    values, divergences = [], []
    for value, published in sorted(entry["bits"].items()):
        seen = scored.get(value, 0)
        measured = -math.log2(seen / total) if seen and total else None
        row = {"value": value, "published_bits": published, "observations": seen,
               "measured_bits": measured}
        if measured is not None:
            row["divergence"] = abs(measured - published)
            divergences.append(row["divergence"])
        values.append(row)
    return {
        "axis": entry["axis"],
        "extractor": entry["extractor"],
        "severity": entry["severity"],
        "scored_transactions": total,
        "unreadable": unreadable,
        "abstained": abstained,
        "values_published": len(entry["bits"]),
        "values_the_cache_shows": sum(1 for row in values if row["observations"]),
        "mean_divergence_bits": (sum(divergences) / len(divergences)) if divergences else None,
        "max_divergence_bits": max(divergences) if divergences else None,
        "values": values,
    }


def build_artifact(snapshot):
    with TemporaryDirectory(prefix="decluster-calibration-") as temporary:
        root = extract_tar_gz(snapshot, temporary)
        cache = root / ".blkcache"
        transactions = load_blkcache(str(cache))
        axes = [_axis(entry, transactions) for entry in library.AXES]
        source = fingerprint_source(str(cache / "*.json"))
        source.update(pattern=".blkcache/*.json", transactions=len(transactions))
    comparable = [axis for axis in axes if axis["mean_divergence_bits"] is not None]
    uncalibratable = sum(axis["values_published"] - axis["values_the_cache_shows"]
                         for axis in axes)
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "dataset": "fs-blkcache-2026-09-04-v1",
        "source": source,
        "measurement": {
            "axes_catalogued": len(axes),
            "axes_the_cache_can_compare": len(comparable),
            "values_published": sum(axis["values_published"] for axis in axes),
            "values_the_cache_never_shows": uncalibratable,
            "mean_divergence_bits": (
                sum(axis["mean_divergence_bits"] for axis in comparable) / len(comparable)
                if comparable else None
            ),
            "largest_divergence": max(
                ((axis["axis"], axis["max_divergence_bits"]) for axis in comparable),
                key=lambda pair: pair[1], default=None,
            ),
            "axes": axes,
        },
        "parameters": {
            "published_population": "~105k uniform whole-chain sample via BigQuery, not preserved",
            "measured_population": "the committed block cache",
            "bits": "minus the base-2 log of a value's share of the scored population",
        },
        "limitations": [
            "this is not a reproduction of the published calibration; the population it used is gone",
            "the cache is block-sampled and era-skewed, so a divergence is expected and its size is "
            "the only thing measured here",
            "a value the cache never shows is counted, not estimated",
            "recalibrating the library on this cache is a separate decision this run does not take",
            "divergence in bits is not an error rate and is not a privacy score",
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
        raise VerificationError("unsupported library-calibration artifact identity")
    measured = build_artifact(snapshot)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    measured = artifact["measurement"]
    axis, worst = measured["largest_divergence"]
    lines = [
        "# The fingerprint library against the population that is still here",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"The shipped bits were measured on a ~105k uniform whole-chain sample that no longer "
        f"exists. This measures the same quantity on the {artifact['source']['transactions']} "
        "transactions of the committed block cache. It is not a reproduction — the populations "
        "differ by construction — and the only thing it establishes is how far apart they land.",
        "",
        "| axis | values | shown by the cache | mean divergence | max |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in measured["axes"]:
        mean = "n/a" if row["mean_divergence_bits"] is None else f"{row['mean_divergence_bits']:.2f}"
        top = "n/a" if row["max_divergence_bits"] is None else f"{row['max_divergence_bits']:.2f}"
        lines.append(
            f"| {row['axis']} | {row['values_published']} | {row['values_the_cache_shows']} | "
            f"{mean} | {top} |"
        )
    lines += [
        "",
        f"Across the {measured['axes_the_cache_can_compare']} axes the cache can compare, the mean "
        f"divergence is **{measured['mean_divergence_bits']:.2f} bits** and the largest single one "
        f"is **{worst:.2f} bits**, on `{axis}`. For scale, the catalogued scorer's whole positive "
        "mean on this same cache is about 15 bits.",
        "",
        f"{measured['values_the_cache_never_shows']} of {measured['values_published']} published "
        "values never appear in the cache, so they cannot be checked against it at all.",
        "",
        "None of this says the shipped table is wrong. It says the part of it a reader can verify "
        "is the part measured here, and that the rest moves by bits rather than by decimals when "
        "the population changes. Whether to recalibrate on this cache is a separate decision, and "
        "`fingerprint-regime-v1` already reports what changes when the weights are fitted to a "
        "snapshot instead of read from the library.",
        "",
    ]
    return "\n".join(lines)


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
