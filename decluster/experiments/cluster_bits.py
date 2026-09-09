"""What a co-spend cluster carries as a quasi-identifier, on committed transactions.

The paper's §2 rests on an asymmetry: a merged transaction contributes about 1.6 bits of ambiguity,
and an established cluster carries far more identifying structure than that, so the partition is
decidable without the merge. The figure behind it was measured on a slice that no longer exists,
which left the argument's load-bearing number unverifiable.

The quantity is the Narayanan--Shmatikov accumulation on real transactions. A cluster's identifier
is the set of external counterparties it pays or is paid by, co-spend edges excluded so the signal
is not circular and its own members excluded because an intra-cluster edge tells an outsider
nothing. Each counterparty is worth `-log2(share of nodes touching it)`: a hub everyone touches is
close to zero, a rare address is many.

The committed cache is block-sampled rather than contiguous, so it holds fewer counterparties per
cluster than a connected slice would. That makes every bit count here a floor, and the comparison
the paper needs — against 1.6 — is one a floor can settle.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from tempfile import TemporaryDirectory

from ..archive_snapshot import extract_tar_gz
from ..cluster import _agg, counterparty_bits
from ..fingerprint_validate import load_blkcache
from ..graph_deanon import _clusters, build
from ..reproducibility import fingerprint_source
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "cluster-bits-v1"
MERGE_AMBIGUITY_BITS = 1.6      # the merge's contribution the asymmetry is stated against
TOPK = 5
THRESHOLDS = (1.6, 10.0, 50.0, 100.0)


class VerificationError(ValueError):
    """The stored result differs from a fresh execution."""


def _rows(transactions):
    sample = [(tx, 0) for tx in transactions]
    union, _full, payments, _cospent = build(sample)
    bits = counterparty_bits(payments)
    rows = []
    for members in _clusters(union, payments).values():
        counterparties = _agg(members, payments) - set(members)
        if not counterparties:
            continue
        per = sorted((bits.get(c, 0.0) for c in counterparties), reverse=True)
        rows.append({"members": len(members), "counterparties": len(counterparties),
                     "total_bits": sum(per), "topk_bits": sum(per[:TOPK])})
    return rows


def build_artifact(snapshot="data/fs-blkcache-2026-09-04.tar.gz"):
    with TemporaryDirectory(prefix="decluster-bits-") as temporary:
        root = extract_tar_gz(snapshot, temporary)
        cache = root / ".blkcache"
        transactions = load_blkcache(str(cache))
        source = fingerprint_source(str(cache / "*.json"))
        source.update(pattern=".blkcache/*.json", transactions=len(transactions))

    rows = [row for row in _rows(transactions) if row["total_bits"] > 0]
    totals = sorted(row["total_bits"] for row in rows)
    floors = sorted(row["topk_bits"] for row in rows)
    quantile = lambda seq, q: seq[min(int(len(seq) * q), len(seq) - 1)] if seq else 0.0
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "dataset": "fs-blkcache-2026-09-04-v1",
        "source": source,
        "parameters": {"topk": TOPK, "merge_ambiguity_bits": MERGE_AMBIGUITY_BITS,
                       "graph": "payment edges only, co-spend excluded"},
        "population": {
            "transactions": len(transactions), "clusters": len(rows),
            "clusters_with_at_most_topk_counterparties":
                sum(1 for row in rows if row["counterparties"] <= TOPK),
        },
        "bits": {
            "median": round(statistics.median(totals), 4) if totals else 0.0,
            "p90": round(quantile(totals, 0.9), 4),
            "max": round(max(totals), 4) if totals else 0.0,
            "median_topk_floor": round(statistics.median(floors), 4) if floors else 0.0,
        },
        "share_at_least": {f"{t:g}": round(sum(1 for v in totals if v >= t) / len(totals), 6)
                           for t in THRESHOLDS} if totals else {},
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


def verify_artifact(artifact, snapshot="data/fs-blkcache-2026-09-04.tar.gz"):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported cluster-bits artifact identity")
    measured = build_artifact(snapshot)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    bits, population = artifact["bits"], artifact["population"]
    share = artifact["share_at_least"]
    merge = artifact["parameters"]["merge_ambiguity_bits"]
    lines = [
        "# What a cluster carries against what a merge hides",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"{population['clusters']} co-spend clusters in {population['transactions']} committed "
        f"transactions, each scored by the rarity of the external counterparties it pays or is paid "
        f"by. Co-spend edges are excluded, so the identifier is not the thing that built the cluster.",
        "",
        "| quantity | bits |",
        "|---|---:|",
        f"| median cluster | {bits['median']:.1f} |",
        f"| p90 cluster | {bits['p90']:.1f} |",
        f"| largest cluster | {bits['max']:.1f} |",
        f"| median, five rarest counterparties only | {bits['median_topk_floor']:.1f} |",
        "",
        "| threshold | share of clusters at or above |",
        "|---:|---:|",
    ]
    for threshold in sorted(share, key=float):
        lines.append(f"| {threshold} bits | {share[threshold]:.1%} |")
    lines.extend([
        "",
        f"The asymmetry the argument needs is the first row against {merge}: a merged transaction "
        f"contributes about {merge} bits of ambiguity, and {share.get(str(merge), 0):.1%} of these "
        f"clusters already carry at least that much, at a median of {bits['median']:.1f}.",
        "",
        f"The five-rarest floor does not test that on this cache: "
        f"{population['clusters_with_at_most_topk_counterparties'] / population['clusters']:.0%} of "
        f"these clusters have at most {artifact['parameters']['topk']} counterparties, so the "
        f"restriction usually keeps the whole set and its median "
        f"({bits['median_topk_floor']:.1f}) repeats the one above it. A slice with richer "
        f"neighbourhoods is what would make that floor say something about dependence between "
        f"counterparties; here it says only that the clusters are small.",
        "",
        "The cache is block-sampled rather than contiguous, so a cluster's counterparties are "
        "undercounted relative to a connected slice and every figure here is a floor. That is the "
        "direction the argument can use: a floor above the merge's contribution settles the "
        "comparison, and a larger slice can only raise it.",
        "",
        "## Reproducibility / provenance",
        "",
        "State 1 in `results/REPRODUCIBILITY.md`: band-pinned on committed data — the artifact is "
        "recomputed from `data/fs-blkcache-2026-09-04.tar.gz` and compared byte for byte.",
    ])
    return "\n".join(lines) + "\n"


def _parser():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("reproduce", "verify"))
    parser.add_argument("--snapshot", default="data/fs-blkcache-2026-09-04.tar.gz")
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
