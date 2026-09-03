import glob
import json
import statistics
from pathlib import Path

import pytest

from decluster import reproducibility as rp
from decluster.fingerprint_validate import load_blkcache
from decluster.fs_ablation import (
    class_conditional_association,
    dependent_clusters,
    group_ablation,
    leave_one_out,
    most_dependent_pairs,
    phi_coefficient,
    run_ablation_study,
)
from decluster.fs_temporal import temporal_split

FIXTURE = Path(__file__).parent / "fixtures" / "fingerprint_blkcache_sample.json"
ROOT = Path(__file__).resolve().parent.parent
BLKCACHE = ROOT / ".blkcache"

# The cluster of mutually correlated script/signature-encoding axes this fixture reliably
# reproduces at the module's default cluster_threshold=0.6 (also found on the full .blkcache
# population, there joined by a fifth field, `nested_segwit`, that this smaller sample does not
# have enough active observations to connect).
SCRIPT_CLUSTER = {"input_script_type", "input_types_present", "pubkey_compression", "sighash"}


def test_phi_coefficient_perfect_agreement_and_disagreement():
    assert phi_coefficient([True, True, False, False], [True, True, False, False]) == 1.0
    assert phi_coefficient([True, True, False, False], [False, False, True, True]) == -1.0


def test_phi_coefficient_none_on_degenerate_margin():
    # every "a" value is True: the a-margin is degenerate, phi is undefined
    assert phi_coefficient([True, True, True], [True, False, True]) is None


def test_phi_coefficient_zero_on_independence():
    a = [True, True, False, False] * 5
    b = [True, False, True, False] * 5
    assert phi_coefficient(a, b) == 0.0


def test_class_conditional_association_is_class_specific_not_pooled():
    """Two fields that each track the label perfectly but in OPPOSITE directions per class:
    pooling classes would show them moving together on some slice of the data by construction of
    the labels, but within either single class they are constant (one value only) and so must
    score as no observation at all -- not as agreement, and not as the strong pooled correlation
    unconditional statistics would report."""
    class Field:
        def __init__(self, name):
            self.name = name

    fields = [Field("a"), Field("b")]
    # within match: a and b always agree; within non-match: a and b always disagree.
    vectors = (
        [{"a": True, "b": True}] * 20 + [{"a": False, "b": False}] * 20 +
        [{"a": True, "b": False}] * 20 + [{"a": False, "b": True}] * 20
    )
    labels = [True] * 40 + [False] * 40
    assoc = class_conditional_association(vectors, labels, fields, min_n=10)
    assert assoc["match"][("a", "b")]["phi"] == 1.0
    assert assoc["non_match"][("a", "b")]["phi"] == -1.0


def test_most_dependent_pairs_ranks_by_larger_magnitude():
    assoc = {
        "match": {("a", "b"): {"phi": 0.9, "n": 50}, ("a", "c"): {"phi": 0.1, "n": 50}},
        "non_match": {("a", "b"): {"phi": 0.2, "n": 50}},
    }
    ranked = most_dependent_pairs(assoc, top_n=2)
    assert ranked[0][0] == ("a", "b")
    assert ranked[1][0] == ("a", "c")


def test_dependent_clusters_groups_transitively_and_drops_singletons():
    assoc = {
        "match": {
            ("a", "b"): {"phi": 0.9, "n": 50},
            ("b", "c"): {"phi": 0.7, "n": 50},
            ("d", "e"): {"phi": 0.1, "n": 50},
        },
        "non_match": {},
    }
    clusters = dependent_clusters(assoc, threshold=0.6)
    assert clusters == [{"a", "b", "c"}]


def test_leave_one_out_reports_a_delta_per_baseline_field():
    with FIXTURE.open() as stream:
        txs = json.load(stream)
    result = leave_one_out(txs, cap=200, seed=0)
    assert set(result["leave_one_out"]) == set(result["baseline"]["fields"])
    for entry in result["leave_one_out"].values():
        assert 0 <= entry["auc"] <= 1


def test_group_ablation_needs_at_least_two_fields():
    with FIXTURE.open() as stream:
        txs = json.load(stream)
    with pytest.raises(ValueError, match="at least two"):
        group_ablation(txs, {"version"}, cap=200, seed=0)


def test_run_ablation_study_shape():
    with FIXTURE.open() as stream:
        txs = json.load(stream)
    result = run_ablation_study(txs, ablation_cap=200, association_cap=200, seed=0)
    assert result["association"]["statistic"].startswith("phi coefficient")
    assert isinstance(result["association"]["clusters"], list)
    assert len(result["group_ablation"]) == len(result["association"]["clusters"])
    for group in result["group_ablation"]:
        assert group["representative"] in group["group"]


def test_removing_the_whole_correlated_cluster_hurts_more_than_keeping_one_representative():
    """The pinned direction, in the style of
    `test_fs_temporal.py::test_fellegi_sunter_beats_the_rarity_baseline_out_of_period`: if a
    cluster of fields is genuinely redundant (each a near-copy of the others' information), then
    dropping every member should cost held-out AUC more than dropping every member but one. A
    verdict here does not depend on which field the model happens to keep, only on group-vs-keep
    outperforming by a pre-registered margin, gated through `reproducibility.separable` on the
    paired per-seed discordant wins rather than read off one run.
    """
    with FIXTURE.open() as stream:
        txs = json.load(stream)

    diffs = []
    for seed in range(6):
        result = group_ablation(txs, SCRIPT_CLUSTER, cap=300, seed=seed)
        diffs.append(result["remove_group_delta"] - result["keep_representative_delta"])

    wins_remove = sum(1 for d in diffs if d > 0)
    wins_keep = sum(1 for d in diffs if d < 0)
    verdict, p = rp.separable(wins_remove, wins_keep, statistics.median(diffs), min_effect=0.001)
    assert verdict == "a", f"diffs={diffs} wins={wins_remove}/{wins_keep} p={p}"


def test_manifest_invariants_are_recomputed_and_match_results_fs_ablation():
    """Mirrors `test_fs_temporal.py`'s manifest test: recompute the population invariants
    `results/RESULTS-fs-ablation.md` depends on directly from `.blkcache`, and assert
    `check_manifest` calls them `ok` against that live recomputation, not just `identity-only`
    against an unchanged byte digest."""
    if not glob.glob(str(BLKCACHE / "*.json")):
        pytest.skip(".blkcache not present in this checkout; population invariants not recomputed")

    txs = load_blkcache(str(BLKCACHE))
    train, test, cutoff = temporal_split(txs, 0.7)
    result = run_ablation_study(txs, ablation_cap=4000, association_cap=8000, seed=0)

    invariants = {
        "transactions": len(txs),
        "split_cutoff": cutoff,
        "train_transactions": len(train),
        "test_transactions": len(test),
        "cluster_threshold": result["association"]["cluster_threshold"],
        "clusters": result["association"]["clusters"],
        "most_dependent_pair": result["association"]["most_dependent_pairs"][0]["fields"],
        "most_dependent_pair_phi_match": result["association"]["most_dependent_pairs"][0]["phi_match"],
        "most_dependent_pair_phi_non_match":
            result["association"]["most_dependent_pairs"][0]["phi_non_match"],
        "baseline_auc": result["leave_one_out"]["baseline"]["auc"],
    }
    status, message = rp.check_manifest("RESULTS-fs-ablation.md", invariants, root=str(ROOT))
    assert status == "ok", message
