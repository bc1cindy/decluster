import math
from decluster.partition_posterior import (
    coassignment, dahl_consensus, posterior_entropy, k_posterior, rhat, calibration)


def test_coassignment_counts_co_clustering_fraction():
    samples = [[0, 0, 1], [0, 1, 1], [0, 0, 1], [0, 0, 1]]
    ca = coassignment(samples)
    assert abs(ca[(0, 1)] - 0.75) < 1e-9   # together in 3 of 4
    assert abs(ca[(1, 2)] - 0.25) < 1e-9


def test_dahl_consensus_picks_a_representative_sample():
    samples = [[0, 0, 1]] * 8 + [[0, 1, 2], [0, 0, 0]]
    cons = dahl_consensus(samples)
    # normalise to compare partition shape
    from decluster.split_merge import _relabel
    assert _relabel(cons) == _relabel([0, 0, 1])


def test_posterior_entropy_zero_when_all_samples_equal():
    assert posterior_entropy([[0, 0, 1]] * 5) == 0.0


def test_k_posterior_sums_to_one():
    kp = k_posterior([[0, 0, 1], [0, 1, 2], [0, 0, 0]])
    assert abs(sum(kp.values()) - 1.0) < 1e-9


def test_rhat_near_one_for_identical_chains():
    chain = [1.0, 1.1, 0.9, 1.0, 1.05]
    assert abs(rhat([chain, list(chain)]) - 1.0) < 0.2


def test_calibration_perfect_predictions_zero_ece():
    # co-assignment equal to labels -> ECE 0
    coassign = {(0, 1): 1.0, (0, 2): 0.0, (1, 2): 0.0}
    labels = {(0, 1): 1, (0, 2): 0, (1, 2): 0}
    assert calibration(coassign, labels) < 1e-9
