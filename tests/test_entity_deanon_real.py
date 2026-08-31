"""Pin the strong Narayanan-Shmatikov claim (cit 24) on a committed real slice: SatoshiDice, a
service whose returning bettors make its house addresses share many common neighbours, is re-linked
by graph structure alone under an *independent* vanity-prefix label (disjoint from co-spend). Slice:
2013-08 blocks 250000-250150 via `bigquery/graph.sql`, reduced to the SatoshiDice sub-graph and
frozen at `tests/fixtures/entity_satoshidice_2013.ndjson.gz`. `results/RESULTS-entity-deanon.md`
reports AUC ~0.72 and mean shared neighbours 7.95; the shared-neighbour figure reproduces exactly on
the sub-graph, the AUC as a band above chance."""
import gzip
import json
import os

from decluster.graph_deanon import evaluate_entity
from decluster.entities import detect_satoshidice

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "entity_satoshidice_2013.ndjson.gz")


def _sample():
    with gzip.open(FIX, "rt") as f:
        return [(json.loads(l), 0) for l in f]


def test_satoshidice_relinked_by_shared_neighbours():
    r = evaluate_entity(_sample(), detect_satoshidice)
    assert r["entity_clusters"] >= 1 and r["pos_pairs"] > 100
    assert r["auc_payment"] >= 0.65            # structural de-anon well above chance (doc ~0.72)
    assert 7.0 <= r["pos_mean"] <= 9.0          # mean shared neighbours (doc 7.95)


BITMEX_FIX = os.path.join(os.path.dirname(__file__), "fixtures", "entity_bitmex_2019.ndjson.gz")


def _bitmex_sample():
    with gzip.open(BITMEX_FIX, "rt") as f:
        return [(json.loads(l), 0) for l in f]


def test_bitmex_hub_is_a_null_control():
    """The paired negative control (RESULTS-entity-deanon.md): BitMEX, a custodial hub whose deposit
    addresses do NOT share returning counterparties, is NOT re-linked by graph structure — AUC at
    chance. This is what makes SatoshiDice a positive rather than an artefact: a service with recurring
    bettors de-anonymizes (0.72), a hub does not (0.50). Slice: 2019-06 blocks 581000-581030."""
    from decluster.entities import detect_bitmex
    r = evaluate_entity(_bitmex_sample(), detect_bitmex)
    assert 0.45 <= r["auc_payment"] <= 0.55        # at chance — no shared-neighbour structure
    assert r["pos_mean"] < 1.0                       # BitMEX deposit addresses share ~no neighbours
