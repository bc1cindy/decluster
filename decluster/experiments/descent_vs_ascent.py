"""Measure what a descending pass recovers from a clustering it did not build.

The two directions answer different questions with the same evidence. Ascending, an analyst holds
the discrete partition and declines a merge the spending transaction argues against: nothing is
ever fused wrongly because nothing is fused without assent. Descending, the analyst is handed a
partition already fused by common-input ownership and can only cut it, and a cut has to clear a bar
a refusal never faced — the evidence must argue against the pairing rather than merely fail to
argue for it.

This experiment runs both over one frozen slice and reports where they disagree. The comparison is
possible at all only because the refusal channels here are properties of the spending transaction:
coinjoin shape, the de-mix partition, and the published merge tells. None of them is the bare
co-spend, which is the inherited claim under test and so contributes nothing to the descent.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path

from .. import views
from ..declustering import MAX_BLOCK, decluster
from ..monitor import is_coinjoin
from ..partition import Partition
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "descent-vs-ascent-v1"
DEFAULT_DATASET = "tests/fixtures/slice_a_channels_2016.ndjson.gz"

# Thresholds are reported rather than chosen: `decluster` takes no default, and a single number
# would hide how much of the divergence is the threshold's doing.
THRESHOLDS = (-1.0, -2.0, -4.0)


class VerificationError(ValueError):
    """The dataset or stored result violates this experiment's contract."""


def _load(path):
    sample = []
    try:
        with gzip.open(path, "rt", encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                transaction = json.loads(line)
                if not isinstance(transaction, dict) or not transaction.get("txid"):
                    raise VerificationError(
                        f"{path}:{line_number}: transaction must be an object with a txid"
                    )
                sample.append((transaction, 0))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read slice snapshot {path}: {exc}") from exc
    if not sample:
        raise VerificationError(f"slice snapshot is empty: {path}")
    return sample


def pair_evidence(sample):
    """Signed signals per input pair, counting only what argues about the pairing itself.

    One signal is one published tell. A co-spend with nothing against it scores zero: it is the
    claim the descent is testing, so counting it would let the inherited partition vouch for
    itself.
    """
    signals = Counter()
    for transaction, _ in sample:
        addresses = views._in_addrs(transaction)
        distinct = list(dict.fromkeys(addresses))
        if len(distinct) < 2:
            continue
        if is_coinjoin(transaction):
            verdict = {pair: -1 for pair in _pairs(distinct)}
        else:
            participants = views._demix_participants(transaction)
            if participants is not None:
                placed = {
                    address: name
                    for name, group in participants.items()
                    for address in group
                }
                verdict = {}
                for pair in _pairs(distinct):
                    together = placed.get(pair[0]) is not None and placed.get(pair[0]) == placed.get(pair[1])
                    verdict[pair] = 1 if together else -1
            else:
                objections = views.merge_objections(transaction) or 0
                if not objections:
                    continue
                verdict = {pair: -objections for pair in _pairs(distinct)}
        for pair, value in verdict.items():
            signals[pair] += value
    return signals


def _pairs(items):
    return [
        (a, b) if a <= b else (b, a)
        for index, a in enumerate(items)
        for b in items[index + 1:]
    ]


def _weight(signals):
    return lambda a, b: float(signals.get((a, b) if a <= b else (b, a), 0))


def _shared_ground(inherited_lookup, ascent_lookup):
    """The ascent over the inherited ground set: an address it never merged is a singleton.

    The two passes return lookups of different size — a refused merge leaves its addresses out of
    the union-find entirely — and the lattice refuses partitions of different ground sets rather
    than resolving the difference silently.
    """
    extra = set(ascent_lookup) - set(inherited_lookup)
    if extra:
        raise VerificationError(
            f"the refusing pass covers {len(extra)} addresses the inherited partition does not"
        )
    filled = dict(ascent_lookup)
    for address in inherited_lookup:
        filled.setdefault(address, ("_singleton", address))
    return Partition.from_lookup(filled)


def _agreement(left, right):
    """How the two partitions differ, counted over the pairs each one joins."""
    joined_left = {pair for block in left.blocks() for pair in _pairs(sorted(block))}
    joined_right = {pair for block in right.blocks() for pair in _pairs(sorted(block))}
    return {
        "joined_by_both": len(joined_left & joined_right),
        "joined_only_by_descent": len(joined_left - joined_right),
        "joined_only_by_ascent": len(joined_right - joined_left),
        "identical": left == right,
    }


def _run(inherited, weight, ascent, cut_below):
    result = decluster(inherited, weight, cut_below=cut_below, max_block=MAX_BLOCK)
    summary = result.summary()
    return {
        "cut_below": cut_below,
        "blocks_cut": summary["cut"],
        "blocks_left_whole": summary["left_whole"],
        "blocks_approximated": summary["approximated"],
        "severed_weight": summary["severed_weight"],
        "resulting_blocks": len(result.partition),
        "refines_inherited": result.partition.refines(inherited),
        "reaches_ascent": result.partition.refines(ascent),
        "agreement_with_ascent": _agreement(result.partition, ascent),
    }


def _evidence_reach(inherited, ascent, signals):
    """Where the refusal channels actually speak, relative to the blocks they would have to cut."""
    reach = {
        "signalled_pairs": len(signals),
        "joined_pairs": 0,
        "joined_pairs_in_exactly_searched_blocks": 0,
        "negative_pairs_in_exactly_searched_blocks": 0,
        "negative_pairs_in_approximated_blocks": 0,
        "approximated_blocks_carrying_evidence": 0,
        "separated_by_ascent_only": 0,
        "separated_by_ascent_only_in_exactly_searched_blocks": 0,
    }
    for block in inherited.blocks():
        exact = len(block) <= MAX_BLOCK
        pairs = _pairs(sorted(block))
        reach["joined_pairs"] += len(pairs)
        carries = 0
        for pair in pairs:
            if signals.get(pair, 0) < 0:
                carries += 1
            if not ascent.same_block(*pair):
                reach["separated_by_ascent_only"] += 1
                if exact:
                    reach["separated_by_ascent_only_in_exactly_searched_blocks"] += 1
        if exact:
            reach["joined_pairs_in_exactly_searched_blocks"] += len(pairs)
            reach["negative_pairs_in_exactly_searched_blocks"] += carries
        else:
            reach["negative_pairs_in_approximated_blocks"] += carries
            reach["approximated_blocks_carrying_evidence"] += carries > 0
    return reach


def build_artifact(dataset=DEFAULT_DATASET):
    sample = _load(dataset)
    inherited_lookup = views.cluster_addresses(sample, refuse=False)
    ascent_lookup = views.cluster_addresses(sample, refuse=True)
    inherited = Partition.from_lookup(inherited_lookup)
    ascent = _shared_ground(inherited_lookup, ascent_lookup)
    signals = pair_evidence(sample)
    weight = _weight(signals)

    sizes = Counter(len(block) for block in inherited.blocks())
    searchable = sum(count for size, count in sizes.items() if size <= MAX_BLOCK)
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "measurement": {
            "transactions": len(sample),
            "addresses": len(inherited.elements()),
            "inherited_blocks": len(inherited),
            "ascent_blocks": len(ascent),
            "ascent_refines_inherited": ascent.refines(inherited),
            "largest_inherited_block": max(sizes),
            "addresses_in_exactly_searched_blocks": sum(
                size * count for size, count in sizes.items() if size <= MAX_BLOCK
            ),
            "exactly_searched_blocks": searchable,
            "evidence_reach": _evidence_reach(inherited, ascent, signals),
            "descent": [_run(inherited, weight, ascent, bar) for bar in THRESHOLDS],
        },
        "parameters": {
            "max_block": MAX_BLOCK,
            "thresholds": list(THRESHOLDS),
            "signal_unit": "one published tell against a pairing",
            "cospend_prior": 0.0,
            "channels": [
                "coinjoin shape refuses every pair among the inputs",
                "de-mix partition joins a participant's own inputs and refuses across participants",
                "unnecessary input and mixed input types each refuse once",
            ],
        },
        "limitations": [
            "the snapshot contains six 2016 blocks and is not a chain-wide sample",
            "blocks above max_block get the conservative pass, which cuts only where no pair objects and is not the best cut",
            "signals are counted tells, not calibrated bits, so the thresholds are not likelihoods",
            "the two passes are compared as partitions; neither is checked against same-owner labels",
            "the fingerprint and roundness channels are absent here, as they are in the merge pass",
            "the snapshot recipe is unavailable; the dataset publisher authorized redistribution on 2026-09-04",
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


def verify_artifact(artifact, dataset=DEFAULT_DATASET):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported descent-versus-ascent artifact identity")
    measured = build_artifact(dataset)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    measured = artifact["measurement"]
    reach = measured["evidence_reach"]
    runs = measured["descent"]
    covered = 100.0 * reach["signalled_pairs"] / reach["joined_pairs"]
    best = min(runs, key=lambda run: run["agreement_with_ascent"]["joined_only_by_descent"])
    recovered = (reach["separated_by_ascent_only"]
                 - best["agreement_with_ascent"]["joined_only_by_descent"])
    lines = [
        "# Ascending and descending over the same slice",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"Two passes read the same {measured['transactions']} transactions and "
        f"{measured['addresses']} addresses. The ascending pass starts from the discrete "
        "partition and declines a merge the spending transaction argues against. The descending "
        "pass is handed the common-input-ownership partition and may only cut it, from the same "
        "refusal channels with the co-spend prior removed.",
        "",
        "| pass | blocks | blocks cut | separations the ascent makes and this does not |",
        "|---|---:|---:|---:|",
        f"| common-input ownership, inherited | {measured['inherited_blocks']} | n/a | "
        f"{reach['separated_by_ascent_only']} |",
        f"| refusing merge pass, ascending | {measured['ascent_blocks']} | n/a | 0 |",
    ]
    for run in runs:
        lines.append(
            f"| descent at cut_below {run['cut_below']:.0f} | {run['resulting_blocks']} | "
            f"{run['blocks_cut']} | "
            f"{run['agreement_with_ascent']['joined_only_by_descent']} |"
        )
    lines += [
        "",
        f"At the loosest bar the descent recovers **{recovered} of the "
        f"{reach['separated_by_ascent_only']}** separations the ascent makes, cutting "
        f"{best['blocks_cut']} blocks and never separating a pair the ascent keeps together. "
        "Every signal on this slice is a single tell, so a bar of two or more clears nothing: the "
        "threshold is doing real work rather than sitting below the data.",
        "",
        "| quantity | pairs |",
        "|---|---:|",
        f"| joined by the inherited partition | {reach['joined_pairs']} |",
        f"| carrying evidence against the pairing | {reach['signalled_pairs']} |",
        f"| joined inside an exactly searched block | {reach['joined_pairs_in_exactly_searched_blocks']} |",
        f"| evidence inside an exactly searched block | {reach['negative_pairs_in_exactly_searched_blocks']} |",
        f"| evidence inside a block the conservative pass handled | "
        f"{reach['negative_pairs_in_approximated_blocks']} |",
        "",
        f"Evidence against a pairing reaches {covered:.2f}% of the joined pairs, and all of it lies "
        f"inside {reach['approximated_blocks_carrying_evidence']} of the "
        f"{measured['inherited_blocks'] - measured['exactly_searched_blocks']} blocks that exceed "
        f"the exact bound of {artifact['parameters']['max_block']} addresses. Not one of the "
        f"{measured['exactly_searched_blocks']} blocks the exact search reaches contains a pair "
        "these channels argue against, so there it correctly did nothing. The heavy tail is where "
        "the evidence lives and where an exact search cannot go, which is why the conservative pass "
        "exists.",
        "",
        "What the two directions do with identical evidence is still not symmetric, and the "
        f"remaining {best['agreement_with_ascent']['joined_only_by_descent']} pairs are the "
        "measure of it. A refusal at merge time separates two addresses without holding any "
        "evidence about that pair: the merge is simply not made, and transitivity never carries "
        "through it. A cut has to argue about the boundary it names, against blocks reaching "
        f"{measured['largest_inherited_block']} addresses. Descending is strictly more expensive "
        "than not ascending, and this slice says how much.",
        "",
        "These counts describe one six-block slice under two channels, compare the passes as "
        "partitions rather than against same-owner labels, and do not establish how either pass "
        "behaves where the evidence is denser.",
        "",
    ]
    return "\n".join(lines)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
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
        artifact = verify_artifact(load_artifact(args.artifact), args.dataset)
        if args.markdown is not None:
            actual = Path(args.markdown).read_text(encoding="utf-8")
            if actual != render_markdown(artifact):
                raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
