import math
from decluster.partition_prior import log_prior


def test_crp_cohesion_matches_factorial_form():
    # CRP EPPF up to constant: alpha**K * prod (s_c - 1)!
    sizes = [3, 1, 2]
    got = log_prior(sizes, kind="crp", alpha=1.5)
    want = 3 * math.log(1.5) + math.lgamma(3) + math.lgamma(1) + math.lgamma(2)
    assert abs(got - want) < 1e-9


def test_microcluster_penalises_one_big_cluster_vs_even_split():
    # Same 10 items: one big cluster should score LOWER (more penalised) than an even split
    big = log_prior([8, 1, 1], kind="microcluster", r=2.0, p=0.5)
    even = log_prior([3, 3, 4], kind="microcluster", r=2.0, p=0.5)
    assert even > big


def test_crp_prefers_the_big_cluster_the_opposite_way():
    # Sanity that the priors genuinely differ in direction (collapse vs anti-collapse)
    big = log_prior([8, 1, 1], kind="crp", alpha=1.0)
    even = log_prior([3, 3, 4], kind="crp", alpha=1.0)
    assert big > even
