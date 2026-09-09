"""The conspicuous-order tables, pinned on the committed slice that produces them.

These numbers were published from an export storing amounts as JSON strings, where `"330" > "1000"`
compares true and every multi-input transaction therefore appeared to argue against itself. The
committed snapshot for the same blocks holds integers, and the corrected figures are asserted here
rather than left as prose a later change could contradict silently.

The doubt gate is the row that moved most: under the string reading it looked like a substantial
intervention, and on the amounts as numbers it moves the partition by one cluster.
"""

import json
from collections import Counter
from pathlib import Path

import pytest

from decluster.tx_addrs import in_addrs
from decluster.views import cluster_addresses, merge_objections

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "amount-channel-812695-812831-v1.json"


@pytest.fixture(scope="module")
def sample():
    if not SOURCE.is_file():
        pytest.skip("the committed amount-channel slice is not present")
    return [(tx, 0) for tx in json.loads(SOURCE.read_text())]


def _partition(sample, **options):
    sizes = Counter(cluster_addresses(sample, **options).values())
    clusters = {root: n for root, n in sizes.items() if n >= 2}
    return len(clusters), max(clusters.values()), sum(clusters.values())


def test_a_majority_of_multi_input_transactions_raises_no_objection(sample):
    multi = [tx for tx, _ in sample if len(tx.get("vin", [])) >= 2]
    counts = Counter(merge_objections(tx) for tx in multi)
    assert len(multi) == 1428
    assert dict(counts) == {0: 855, 1: 512, 2: 61}
    assert counts[0] / len(multi) > 0.5, (
        "the conspicuous tier is no longer a majority, which is the premise the merge order rests on")


def test_the_slice_is_the_one_the_documents_describe(sample):
    assert len(sample) == 5491
    assert len({a for tx, _ in sample for a in in_addrs(tx)}) == 14113
    assert _partition(sample, refuse=False)[0] == 889


def test_refusal_moves_the_partition_and_the_doubt_gate_barely_does(sample):
    naive = _partition(sample, refuse=False)
    refusing = _partition(sample, refuse=True)
    gated = _partition(sample, refuse=True, doubt_min_side=2)
    assert naive == (889, 996, 9960)
    assert refusing == (868, 996, 9109)
    assert gated == (869, 996, 9009)
    assert gated[0] - refusing[0] == 1, (
        "the doubt gate has stopped being nearly inert on this slice; the document says it moves the "
        "partition by one cluster")


def test_the_order_the_merges_are_taken_in_changes_nothing(sample):
    """Union-find is order-independent, and the one state-dependent decision is taken in sample
    order under both settings, so staging must not move either partition."""
    assert _partition(sample, refuse=True) == _partition(sample, refuse=True, staged=True)
    assert (_partition(sample, refuse=True, doubt_min_side=2)
            == _partition(sample, refuse=True, staged=True, doubt_min_side=2))
