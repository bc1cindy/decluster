"""Change labels that read values and types rather than co-spend, on committed transactions.

Change identification is validated against a label, and a label drawn from co-spend clustering
validates the fingerprints with the thing the fingerprints are meant to extend. The value-based
special cases break that circle: the output smaller than every input must be the change, an output
whose value is a round number is the deliberate payment, and neither reads an address relation.

The figures this replaces were taken on downloads outside the repository, so nobody could check them
and nobody could take them again. What the committed block cache supports is the offline half: how
often each within-transaction predictor agrees with each label, and how often the labels agree with
each other. The onward-spend half needs a transaction's change output to be spent inside the same
data, which a block-sampled cache almost never holds; the count is recorded here rather than
asserted away, because it is the reason that arm is absent.

The agreement matrix is where the labels stop being four votes. Reuse of an input address forces the
output's script type to match an input's, so wherever both labels are defined they cannot disagree —
a dependence in the labels themselves, not a corroboration between them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ..archive_snapshot import extract_tar_gz
from ..change_gt import is_candidate
from ..change_slice import index_slice, slice_fetchers
from ..change_special import (agreement_matrix, build_gt_special, label_address_reuse,
                              label_optimal_change, label_round_number, label_type_match,
                              within_tx_rates)
from ..fingerprint_validate import load_blkcache
from ..reproducibility import fingerprint_source
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "special-change-labels-v1"
SNAPSHOT = "data/fs-blkcache-2026-09-04.tar.gz"

LABELS = {"optimal_change": label_optimal_change, "round_number": label_round_number,
          "type_match": label_type_match, "address_reuse": label_address_reuse}


class VerificationError(ValueError):
    """The stored result differs from a fresh execution."""


def _load(snapshot):
    with TemporaryDirectory(prefix="decluster-special-") as temporary:
        cache = extract_tar_gz(snapshot, temporary) / ".blkcache"
        transactions = load_blkcache(str(cache))
        source = fingerprint_source(str(cache / "*.json"))
    source.update(pattern=".blkcache/*.json", transactions=len(transactions))
    return transactions, source


def _onward_reach(transactions, labelled):
    """How many labelled transactions have an output spent inside the same data.

    The per-axis onward-spend test votes for the output whose spender carries the same fingerprint,
    so it needs the spender. Block sampling puts it outside the cache for almost every transaction,
    which bounds the arm rather than merely making it noisy.
    """
    by_txid, spender, _uf = index_slice(transactions)
    _get_tx, get_outspends = slice_fetchers(by_txid, spender)
    reach = {}
    for name, ground in labelled.items():
        spends = [[entry["spent"] for entry in get_outspends(record["tx"]["txid"])[:2]]
                  for record in ground]
        reach[name] = {"labels": len(ground),
                       "one_output_spent": sum(1 for s in spends if any(s)),
                       "both_outputs_spent": sum(1 for s in spends if len(s) == 2 and all(s))}
    return reach


def build_artifact(snapshot=SNAPSHOT):
    transactions, source = _load(snapshot)
    labelled = {name: build_gt_special(transactions, labeler)
                for name, labeler in LABELS.items()}

    within = []
    for name, ground in sorted(labelled.items()):
        for predictor, (tpr, fpr, coverage) in sorted(within_tx_rates(ground).items()):
            decided = tpr + fpr
            within.append({"label": name, "predictor": predictor,
                           "tpr": round(tpr, 6), "fpr": round(fpr, 6),
                           "coverage": round(coverage, 6),
                           "precision": round(tpr / decided, 6) if decided else None})

    agreement = [{"a": a, "b": b, **counts}
                 for (a, b), counts in sorted(agreement_matrix(labelled).items())]

    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "dataset": "fs-blkcache-2026-09-04-v1",
        "source": source,
        "parameters": {"labels": sorted(LABELS), "predictors": ["address_reuse", "round_number"]},
        "population": {
            "transactions": len(transactions),
            "two_output_candidates": sum(1 for tx in transactions if is_candidate(tx)),
            "labels": {name: len(ground) for name, ground in sorted(labelled.items())},
        },
        "within_tx": within,
        "agreement": agreement,
        "onward_spend_reach": _onward_reach(transactions, labelled),
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


def verify_artifact(artifact, snapshot=SNAPSHOT):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported special-change artifact identity")
    measured = build_artifact(snapshot)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def _row(rows, label, predictor):
    return next(r for r in rows if r["label"] == label and r["predictor"] == predictor)


def render_markdown(artifact):
    population, within = artifact["population"], artifact["within_tx"]
    reach = artifact["onward_spend_reach"]
    counts = population["labels"]
    forced = next(r for r in artifact["agreement"]
                  if {r["a"], r["b"]} == {"address_reuse", "type_match"})
    lines = [
        "# Change labels that do not read co-spend",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"{population['transactions']} committed transactions, {population['two_output_candidates']} "
        f"of them two-output candidates. Each label picks the change output from values or script "
        f"types alone, so none of them reads the address relation the fingerprints are meant to "
        f"extend.",
        "",
        "| label | transactions it labels |",
        "|---|---:|",
    ]
    lines.extend(f"| {name} | {count} |" for name, count in counts.items())
    lines.extend([
        "",
        "## Within-transaction predictors against each label",
        "",
        "| label | predictor | TPR | FPR | coverage | precision |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for row in within:
        precision = "—" if row["precision"] is None else f"{row['precision']:.3f}"
        lines.append(f"| {row['label']} | {row['predictor']} | {row['tpr']:.3f} | "
                     f"{row['fpr']:.3f} | {row['coverage']:.3f} | {precision} |")
    optimal_round = _row(within, "optimal_change", "round_number")
    optimal_reuse = _row(within, "optimal_change", "address_reuse")
    lines.extend([
        "",
        f"Against the value label, the round-number heuristic is right {optimal_round['precision']:.2f} "
        f"of the time it commits, on {optimal_round['coverage']:.0%} of the labelled transactions, and "
        f"address reuse {optimal_reuse['precision']:.2f} on {optimal_reuse['coverage']:.0%}. Two "
        f"universal heuristics agreeing with a label neither of them reads.",
        "",
        "A predictor scored against its own label is self-agreement and not corroboration: the "
        "round-number rows under the `round_number` label, and the address-reuse rows under "
        "`address_reuse`, read the same fact twice and are reported only so the table is complete.",
        "",
        "## Do the labels agree with each other",
        "",
        "| label | label | both label | agree | disagree |",
        "|---|---|---:|---:|---:|",
    ])
    for row in artifact["agreement"]:
        lines.append(f"| {row['a']} | {row['b']} | {row['both']} | {row['agree']} | "
                     f"{row['disagree']} |")
    lines.extend([
        "",
        f"`address_reuse` and `type_match` agree on all {forced['both']} transactions both label, "
        "and that is arithmetic rather than evidence: an output reusing an input address carries an "
        "input's script type, so the type rule can only select the same output or abstain. They are "
        "one label counted twice, which is the number a corroboration between them would "
        "double-count.",
        "",
        "## The onward-spend arm is not measured here",
        "",
        "Voting for the output whose *spender* repeats the transaction's fingerprint needs that "
        "spender to be in the data. The cache is block-sampled, so it is usually not:",
        "",
        "| label | labelled | one output spent inside | both spent inside |",
        "|---|---:|---:|---:|",
    ])
    for name, row in reach.items():
        lines.append(f"| {name} | {row['labels']} | {row['one_output_spent']} | "
                     f"{row['both_outputs_spent']} |")
    optimal = reach["optimal_change"]
    lines.extend([
        "",
        f"At {optimal['both_outputs_spent']} transactions with both outputs spent inside the cache, "
        "the per-axis rates that arm would report are not a measurement. Getting it needs a "
        "contiguous export deep enough to hold each change output's spender, which is a collection "
        "and not a method — state 4 in `results/REPRODUCIBILITY.md`.",
        "",
        "## Reproducibility / provenance",
        "",
        "State 1 in `results/REPRODUCIBILITY.md`: band-pinned on committed data — the artifact is "
        f"recomputed from `{SNAPSHOT}` and compared byte for byte.",
    ])
    return "\n".join(lines) + "\n"


def _parser():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("reproduce", "verify"))
    parser.add_argument("--snapshot", default=SNAPSHOT)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--markdown", required=True)
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
