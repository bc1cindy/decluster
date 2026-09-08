"""How small a cut separates a coin from its origins, on committed transactions.

The framework states robust connectivity as a property of a cut: no small cut should separate an
output from the mass of its candidate origin coins. Nothing here measured that. `path_count`
accumulates route mass, and its own docstring says why that is a different number — many routes may
run through one coin, so a large count is consistent with a cut of one.

The reading is k-bounded, following the literature on all-pairs bounded min-cuts: what matters is
which coins have a *small* cut, not the exact value where it is large. A coin with two hundred
disjoint routes and a coin with fifty are both out of reach; a coin with one is not.

Two bounds the numbers carry. The walk stops at a fixed depth and at coins the slice does not hold,
so every cut here is a lower bound — a deeper walk can only find more routes, never fewer. And a
route is counted, not weighted: the value it could carry is the plausible-flow half of the property,
which no module in this repository computes.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from .. import ancestry
from ..archive_snapshot import extract_tar_gz
from ..disjoint_routes import TARGET_VALUE, route_capacity
from ..fingerprint_validate import load_blkcache
from ..reproducibility import fingerprint_source
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "route-capacity-v1"
DEPTH = 5
SMALL = 3            # the k-bounded frontier: at or below this, a cut is cheap


class VerificationError(ValueError):
    """The stored result differs from a fresh execution."""


def build_artifact(snapshot="data/fs-blkcache-2026-09-04.tar.gz"):
    with TemporaryDirectory(prefix="decluster-routes-") as temporary:
        root = extract_tar_gz(snapshot, temporary)
        cache = root / ".blkcache"
        transactions = load_blkcache(str(cache))
        source = fingerprint_source(str(cache / "*.json"))
        source.update(pattern=".blkcache/*.json", transactions=len(transactions))

    index = {tx["txid"]: tx for tx in transactions}
    targets = sorted({(tx["txid"], 0) for tx in transactions
                      if sum(1 for vin in tx["vin"] if vin.get("txid") in index) >= 2})

    capacity, plausible, excess, boundary = Counter(), Counter(), Counter(), Counter()
    measured = 0
    for target in targets:
        graph = ancestry.build_extended_graph(
            target, depth=DEPTH, fetch=index.get,
            link_oracle=ancestry.value_flow_link_oracle)
        origins = len(graph.absorbers)
        if not origins:
            continue
        k, _routes = route_capacity(graph, target)
        payable, _ = route_capacity(graph, target, carries=TARGET_VALUE)
        measured += 1
        capacity[k] += 1
        plausible[payable] += 1
        excess[origins - k] += 1
        boundary["fetch_missing"] += graph.fetch_missing
        boundary["depth_capped"] += len(graph.depth_capped)
        boundary["coinbase"] += len(graph.source_absorbers)

    small = sum(count for k, count in capacity.items() if k <= SMALL)
    overstated = sum(count for gap, count in excess.items() if gap > 0)
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "dataset": "fs-blkcache-2026-09-04-v1",
        "source": source,
        "parameters": {"depth": DEPTH, "small_cut_at_most": SMALL,
                       "link_oracle": "value_flow_link_oracle"},
        "population": {"targets": len(targets), "measured": measured},
        "capacity": {str(k): capacity[k] for k in sorted(capacity)},
        "capacity_carrying_the_coin": {str(k): plausible[k] for k in sorted(plausible)},
        "origin_excess": {str(gap): excess[gap] for gap in sorted(excess)},
        "readings": {
            "cut_of_one": capacity[1],
            "cut_of_one_carrying_the_coin": plausible[1],
            "no_route_carries_the_coin": plausible[0],
            "cut_at_most_small": small,
            "origin_set_overstates": overstated,
            "largest_cut": max(capacity) if capacity else 0,
        },
        "boundary_causes": dict(sorted(boundary.items())),
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
        raise VerificationError("unsupported route-capacity artifact identity")
    measured = build_artifact(snapshot)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    population, readings = artifact["population"], artifact["readings"]
    share = lambda n: f"{n} ({n / population['measured']:.0%})"
    lines = [
        "# How small a cut separates a coin from its origins",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"{population['measured']} coins in the committed cache have an ancestry the slice can walk. "
        f"For each, the number of routes back to its candidate origins that share no coin — the "
        f"size of the cut that would separate it.",
        "",
        "| routes | coins | coins, routes able to carry the coin |",
        "|---:|---:|---:|",
    ]
    carrying = artifact["capacity_carrying_the_coin"]
    for k in sorted({*artifact["capacity"], *carrying}, key=int):
        lines.append(f"| {k} | {artifact['capacity'].get(k, 0)} | {carrying.get(k, 0)} |")
    lines.extend([
        "",
        f"**{share(readings['cut_of_one'])} of these coins are separated from their entire ancestry "
        f"by removing one coin**, and {share(readings['cut_at_most_small'])} by removing at most "
        f"{artifact['parameters']['small_cut_at_most']}. The framework asks that no small cut do "
        f"this. At the other end the distribution reaches {readings['largest_cut']} routes, so "
        f"redundancy varies by orders of magnitude between coins in one slice.",
        "",
        f"That count treats every route alike, and the specification does not: a path worth less "
        f"than the amount in question may have been removed before the question is asked. Pruning "
        f"each coin's routes to those that could have carried its own value "
        f"**takes the single-coin cut from {share(readings['cut_of_one'])} to "
        f"{share(readings['cut_of_one_carrying_the_coin'])}**, and leaves "
        f"{share(readings['no_route_carries_the_coin'])} with no route able to carry the coin at "
        f"all. Counting routes without their value overstates redundancy, in the same direction and "
        f"for the same reason as counting origins without their overlap.",
        "",
        f"**Counting origins overstates that redundancy for {share(readings['origin_set_overstates'])} "
        f"of them.** A coin's origin set says how many places its value could have come from; the cut "
        f"says how many of those a separation would have to defeat, and the two are not the same "
        f"number because routes share coins. That difference is the reason this is measured rather "
        f"than counted.",
        "",
        f"Both readings are lower bounds, and one boundary count says how loose. The walk stopped "
        f"{artifact['boundary_causes']['fetch_missing']} times because the slice holds no record of "
        f"a parent, against {artifact['boundary_causes']['depth_capped']} times at the depth limit: "
        f"almost every origin here is the edge of the sample rather than a coinbase or a genuine "
        f"end of provenance. A cut measured to that edge can only grow on a contiguous export, so "
        f"these are the cuts the committed data can already show and not a ceiling on redundancy. "
        f"Read the shape — that a tenth of coins are separated by one coin while others carry "
        f"{artifact['readings']['largest_cut']} routes — rather than the level.",
        "",
        "The value dimension here is a threshold, not an optimisation: a coin either can or cannot "
        "carry the amount, and pruning on that is as cheap as the cut itself. Choosing which routes "
        "carry how much — the k-splittable formulation — is the hard problem and is not this one.",
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
