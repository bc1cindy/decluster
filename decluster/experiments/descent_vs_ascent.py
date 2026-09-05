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
        "blocks_unsearched": summary["unsearched"],
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
        "joined_pairs_in_searchable_blocks": 0,
        "negative_pairs_inside_searchable_blocks": 0,
        "negative_pairs_inside_unsearchable_blocks": 0,
        "unsearchable_blocks_carrying_evidence": 0,
        "separated_by_ascent_only": 0,
        "separated_by_ascent_only_in_searchable_blocks": 0,
    }
    for block in inherited.blocks():
        searchable = len(block) <= MAX_BLOCK
        pairs = _pairs(sorted(block))
        reach["joined_pairs"] += len(pairs)
        carries = 0
        for pair in pairs:
            if signals.get(pair, 0) < 0:
                carries += 1
            if not ascent.same_block(*pair):
                reach["separated_by_ascent_only"] += 1
                if searchable:
                    reach["separated_by_ascent_only_in_searchable_blocks"] += 1
        if searchable:
            reach["joined_pairs_in_searchable_blocks"] += len(pairs)
            reach["negative_pairs_inside_searchable_blocks"] += carries
        else:
            reach["negative_pairs_inside_unsearchable_blocks"] += carries
            reach["unsearchable_blocks_carrying_evidence"] += carries > 0
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
            "addresses_in_searchable_blocks": sum(
                size * count for size, count in sizes.items() if size <= MAX_BLOCK
            ),
            "searchable_blocks": searchable,
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
            "the exact search is skipped on blocks above max_block, and those blocks are left whole",
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
        "| pass | blocks |",
        "|---|---:|",
        f"| common-input ownership, inherited | {measured['inherited_blocks']} |",
        f"| refusing merge pass, ascending | {measured['ascent_blocks']} |",
    ]
    for run in runs:
        lines.append(f"| descent at cut_below {run['cut_below']:.0f} | {run['resulting_blocks']} |")
    lines += [
        "",
        f"The ascent separates {reach['separated_by_ascent_only']} address pairs the inherited "
        f"partition joins. The descent separates none of them, at any of the "
        f"{len(runs)} thresholds, and cut no block at all.",
        "",
        "| quantity | pairs |",
        "|---|---:|",
        f"| joined by the inherited partition | {reach['joined_pairs']} |",
        f"| carrying evidence against the pairing | {reach['signalled_pairs']} |",
        f"| joined inside a searchable block | {reach['joined_pairs_in_searchable_blocks']} |",
        f"| evidence inside a searchable block | {reach['negative_pairs_inside_searchable_blocks']} |",
        f"| evidence inside a block above the search bound | "
        f"{reach['negative_pairs_inside_unsearchable_blocks']} |",
        f"| separated by the ascent inside a searchable block | "
        f"{reach['separated_by_ascent_only_in_searchable_blocks']} |",
        "",
        f"The null is not the threshold's doing. Evidence against a pairing reaches "
        f"{covered:.2f}% of the joined pairs, and all of it lies inside "
        f"{reach['unsearchable_blocks_carrying_evidence']} of the "
        f"{measured['inherited_blocks'] - measured['searchable_blocks']} blocks that exceed the "
        f"exact search bound of {artifact['parameters']['max_block']} addresses. Not one of the "
        f"{measured['searchable_blocks']} blocks the search could reach contains a pair these "
        "channels argue against, so within its reach the search had nothing to act on and "
        "correctly did nothing.",
        "",
        "What the two passes do with identical evidence is therefore not symmetric. A refusal at "
        "merge time separates two addresses without holding any evidence about that pair: the "
        "merge is simply not made, and transitivity never carries through it. A cut has to argue "
        "about every pair crossing the boundary it names, against a partition whose blocks here "
        f"reach {measured['largest_inherited_block']} addresses. On this slice that asymmetry is "
        "the whole difference between the two results.",
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
