import glob
import json
import os
import statistics
from pathlib import Path

import pytest

from decluster import reproducibility as rp
from decluster.fingerprint_validate import load_blkcache
from decluster.fs_temporal import (
    _height,
    _score_metrics,
    evaluate_temporal,
    temporal_split,
    weak_label_pairs,
)


FIXTURE = Path(__file__).parent / "fixtures" / "fingerprint_blkcache_sample.json"
ROOT = Path(__file__).resolve().parent.parent
BLKCACHE = ROOT / ".blkcache"


def test_temporal_evaluation_uses_late_weak_labels_and_same_baseline_pairs():
    with FIXTURE.open() as stream:
        txs = json.load(stream)
    result = evaluate_temporal(txs, cap=200, seed=7)
    assert result["label_provenance"]["independently_verified"] is False
    assert result["label_provenance"]["kind"] == "weak_labels"
    assert result["split"]["train_height"][1] < result["split"]["test_height"][0]
    assert result["pairs"]["test_positive"] == result["pairs"]["test_negative"]
    assert result["comparison"]["same_test_pairs"] is True
    assert 0 <= result["fellegi_sunter"]["auc"] <= 1
    assert 0 <= result["rarity_baseline"]["auc"] <= 1
    assert "brier" in result["fellegi_sunter"]["calibration"]


def test_fellegi_sunter_beats_the_rarity_baseline_out_of_period():
    """The direction RESULTS-fs-temporal.md publishes, pinned on committed data.

    `test_temporal_evaluation_uses_late_weak_labels_and_same_baseline_pairs` asserts only that both
    AUCs are in [0, 1], which a constant scorer satisfies. This asserts the sign: on the identical
    held-out pairs, the fitted Fellegi-Sunter model must beat the fixed-rarity `LibraryScorer`.

    The fixture is a real block-cache sample, not one constructed to display this direction — per
    `results/REPRODUCIBILITY.md`, a direction is only pinned by data that could have shown the
    opposite. The verdict goes through `reproducibility.separable` on the paired per-seed discordant
    wins, with a pre-registered minimum effect, rather than being read off one run.
    """
    with FIXTURE.open() as stream:
        txs = json.load(stream)

    deltas = []
    for seed in range(6):
        result = evaluate_temporal(txs, cap=300, seed=seed)
        assert result["comparison"]["same_test_pairs"] is True
        deltas.append(result["fellegi_sunter"]["auc"] - result["rarity_baseline"]["auc"])

    wins_fs = sum(1 for d in deltas if d > 0)
    wins_rarity = sum(1 for d in deltas if d < 0)
    verdict, p = rp.separable(wins_fs, wins_rarity, statistics.median(deltas), min_effect=0.01)
    assert verdict == "a", f"deltas={deltas} wins={wins_fs}/{wins_rarity} p={p}"


def test_temporal_split_rejects_missing_height():
    with pytest.raises(ValueError, match="block_height"):
        temporal_split([{"txid": "a"}, {"txid": "b"}])


def test_auc_is_exact_and_ties_get_half_credit():
    assert _score_metrics([3, 2, 2, 1], [True, True, False, False])["auc"] == 0.875


def test_manifest_invariants_are_recomputed_and_match_results_fs_temporal():
    """results/manifests/RESULTS-fs-temporal.json records population invariants that a byte digest
    of .blkcache/ cannot see; check_manifest only compares them when a caller recomputes and passes
    them in, so this is that caller. Recomputing the uncapped pair counts needs no rng result
    (positive pairs are never sampled at this cap), so a fixed large cap is deterministic."""
    if not glob.glob(str(BLKCACHE / "*.json")):
        pytest.skip(".blkcache not present in this checkout; population invariants not recomputed")

    txs = load_blkcache(str(BLKCACHE))
    heights = sorted({_height(tx) for tx in txs})
    train, test, cutoff = temporal_split(txs, 0.7)
    _, train_labels = weak_label_pairs(train, cap=10**7, seed=0)
    _, test_labels = weak_label_pairs(test, cap=10**7, seed=0)

    invariants = {
        "transactions": len(txs),
        "height_min": heights[0],
        "height_max": heights[-1],
        "distinct_heights": len(heights),
        "split_cutoff": cutoff,
        "train_transactions": len(train),
        "test_transactions": len(test),
        "train_positive_pairs_available": sum(train_labels),
        "test_positive_pairs_available": sum(test_labels),
    }
    status, message = rp.check_manifest("RESULTS-fs-temporal.md", invariants, root=str(ROOT))
    assert status == "ok", message
