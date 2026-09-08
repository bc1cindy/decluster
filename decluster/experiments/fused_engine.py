"""What each evidence channel adds when the engine fuses them, on committed transactions.

The engine is the thesis: `cluster_refined` refuses a co-spend the merge-only heuristic would take,
by fusing signed bits from several channels. Every channel had a canonical run of its own and the
fusion had none — it was exercised by unit tests and by scripts over data this repository does not
ship, so the object the argument rests on was the one object no published artifact executed.

This runs the engine over the committed block-cache slice as a ladder: co-spend alone, then each
channel switched on in turn. The quantity of interest is the delta, not the level. A channel that
moves nothing here has not been shown useless — the slice is block-sampled rather than contiguous,
and the amount channel in particular is refuse-only and gated behind fingerprint disagreement, so it
can only speak where the fingerprint already objects.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from ..archive_snapshot import extract_tar_gz
from ..cluster import cluster_naive, cluster_refined
from ..combiner import Combiner
from ..fingerprint_validate import load_blkcache
from ..reproducibility import fingerprint_source
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "fused-engine-v1"


class VerificationError(ValueError):
    """The stored result differs from a fresh execution."""


def _slice_inputs(transactions):
    """Nodes, counterparty sets and depth-1 provenance signatures, all read off the slice."""
    index = {tx["txid"]: tx for tx in transactions}
    cospends = [tx for tx in transactions
                if len([v for v in tx["vin"] if v.get("txid") in index]) >= 2]
    nodes = sorted({v["txid"] for tx in cospends for v in tx["vin"] if v.get("txid") in index})
    neighbours = {n: {o.get("scriptpubkey_address") for o in index[n]["vout"]
                      if o.get("scriptpubkey_address")} for n in nodes}
    signatures = {n: {v["txid"]: 1.0 for v in index[n]["vin"] if v.get("txid")} for n in nodes}
    rarity = Counter(origin for signature in signatures.values() for origin in signature)
    return index, cospends, nodes, neighbours, signatures, dict(rarity)


def _arm(name, nodes, combiner, fetch, **options):
    groups, refused, linked = cluster_refined(nodes, combiner, fetch=fetch, **options)
    return {
        "arm": name,
        "groups": len(groups),
        "refused_cospends": len(refused),
        "added_links": len(linked),
        "largest_group": max((len(group) for group in groups), default=0),
    }


def build_artifact(snapshot):
    with TemporaryDirectory(prefix="decluster-fused-") as temporary:
        root = extract_tar_gz(snapshot, temporary)
        cache = root / ".blkcache"
        transactions = load_blkcache(str(cache))
        source = fingerprint_source(str(cache / "*.json"))
        source.update(pattern=".blkcache/*.json", transactions=len(transactions))

    index, cospends, nodes, neighbours, signatures, rarity = _slice_inputs(transactions)
    fetch = index.__getitem__
    combiner = Combiner.from_library()
    topology = {"neigh": neighbours}
    provenance = {"provenance": True, "signatures": signatures, "rarity": rarity}

    baseline = cluster_naive(nodes, fetch=fetch)
    ladder = [
        _arm("fingerprint", nodes, combiner, fetch, amount=False),
        _arm("fingerprint+amount", nodes, combiner, fetch, amount=True),
        _arm("fingerprint+amount+topology", nodes, combiner, fetch, amount=True, **topology),
        _arm("fingerprint+amount+topology+provenance", nodes, combiner, fetch,
             amount=True, **topology, **provenance),
        _arm("all five channels", nodes, combiner, fetch,
             amount=True, **topology, **provenance, subsetsum=True),
    ]
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "dataset": "fs-blkcache-2026-09-04-v1",
        "source": source,
        "population": {
            "transactions": len(transactions),
            "cospend_transactions": len(cospends),
            "two_in_two_out_cospends": sum(
                1 for tx in cospends if len(tx["vin"]) == 2 and len(tx["vout"]) == 2),
            "nodes": len(nodes),
        },
        "cospend_baseline": {
            "arm": "co-spend union-find",
            "groups": len(baseline),
            "refused_cospends": 0,
            "added_links": 0,
            "largest_group": max((len(group) for group in baseline), default=0),
        },
        "ladder": ladder,
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
        raise VerificationError("unsupported fused-engine artifact identity")
    measured = build_artifact(snapshot)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    population = artifact["population"]
    rows = [artifact["cospend_baseline"], *artifact["ladder"]]
    lines = [
        "# What each channel adds when the engine fuses them",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"{population['transactions']} committed transactions hold {population['cospend_transactions']} "
        f"co-spends over {population['nodes']} funding transactions. The engine judges those co-spends; "
        f"the merge-only baseline takes every one of them.",
        "",
        "| arm | groups | refused co-spends | added links | largest group |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(f"| {row['arm']} | {row['groups']} | {row['refused_cospends']} | "
                     f"{row['added_links']} | {row['largest_group']} |")

    baseline, *ladder = rows
    fingerprint, _amount, topology, provenance, full = ladder
    lines.extend([
        "",
        f"The fingerprint channel is what moves the partition: it adds {fingerprint['added_links']} "
        f"links the co-spend missed and takes the largest group from {baseline['largest_group']} to "
        f"{fingerprint['largest_group']}. Refusal is the smaller effect and the one the thesis is "
        f"about — {fingerprint['refused_cospends']} co-spends declined that the baseline merges.",
        "",
        f"Topology and provenance pull in opposite directions, which is the point of fusing them. "
        f"Adding the cluster-level topology takes refusals from {fingerprint['refused_cospends']} to "
        f"{topology['refused_cospends']}: it corroborates merges the fingerprint alone objected to. "
        f"Adding provenance-disjointness takes them to {provenance['refused_cospends']}, cutting "
        f"pairs whose ancestry does not overlap.",
        "",
        f"The amount channel and the subset-sum de-mix move nothing here, and the reason is "
        f"structural rather than empirical: both are refuse-only and gated behind fingerprint "
        f"disagreement, so they can only speak on the pairs the fingerprint already objects to. "
        f"The slice holds {population['two_in_two_out_cospends']} two-input two-output co-spends, "
        f"the only shape the roundness re-partition judges.",
        "",
        "The provenance signature here is depth-1 — a node's in-slice funders — because the slice is "
        "block-sampled rather than contiguous. A deeper walk needs a contiguous export.",
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
