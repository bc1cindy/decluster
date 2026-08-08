import math
import random
from collections import Counter
from decluster.partition_model import Evidence, log_posterior
from decluster.split_merge import (
    gibbs_sweep, enumerate_posterior, split_merge_move, sample, run_chains,
)


def _ev(cat_vals, bases, link=None, cannot=None, conc=1.0, beta=1.0):
    return Evidence(n=len(cat_vals), cat_vals=cat_vals, bases=bases, conc=conc,
                    link=link or {}, cannot=cannot or set(), beta=beta)


def test_enumerate_posterior_normalises():
    ev = _ev([["A"], ["A"], ["B"]], [{"A": 0.5, "B": 0.5}])
    dist = enumerate_posterior(ev)
    assert abs(sum(p for _, p in dist) - 1.0) < 1e-9


def test_gibbs_marginals_match_enumeration_on_small_case():
    ev = _ev([["A"], ["A"], ["B"]], [{"A": 0.5, "B": 0.5}], beta=0.0, conc=1.0)
    # exact P(0,1 same cluster)
    dist = enumerate_posterior(ev)
    exact = sum(p for part, p in dist
                if any(0 in b and 1 in b for b in part))
    rng = random.Random(0)
    labels = [0, 1, 2]
    co = 0
    N = 4000
    for _ in range(N):
        labels = gibbs_sweep(labels, ev, rng, "microcluster", {})
        if labels[0] == labels[1]:
            co += 1
    assert abs(co / N - exact) < 0.05


def test_gibbs_full_distribution_matches_enumeration():
    # Catches per-partition bias the single-marginal test misses (the removed-node bug: the
    # candidate set must be built from the OTHER nodes' clusters after removing i, not from
    # the full label vector still containing i's own cluster).
    ev = _ev([["A"], ["A"], ["B"]], [{"A": 0.5, "B": 0.5}], beta=0.0, conc=1.0)
    exact = {tuple(sorted(part)): p for part, p in enumerate_posterior(ev)}
    rng = random.Random(0)
    labels = [0, 1, 2]
    counts = {}
    N = 20000
    for _ in range(N):
        labels = gibbs_sweep(labels, ev, rng, "microcluster", {})
        blocks = tuple(sorted(tuple(sorted(k for k in range(ev.n) if labels[k] == c))
                              for c in sorted(set(labels))))
        counts[blocks] = counts.get(blocks, 0) + 1
    emp = {k: v / N for k, v in counts.items()}
    # max per-partition absolute difference must be small (the old buggy sampler hit ~0.12)
    worst = max(abs(emp.get(part, 0.0) - p) for part, p in exact.items())
    assert worst < 0.05


def test_gibbs_never_merges_cannot_link():
    ev = _ev([["A"], ["A"]], [{"A": 1.0}], cannot={frozenset({0, 1})})
    rng = random.Random(1)
    labels = [0, 1]
    for _ in range(200):
        labels = gibbs_sweep(labels, ev, rng, "microcluster", {})
        assert labels[0] != labels[1]


def _partition_key(labels, n):
    return tuple(sorted(tuple(sorted(k for k in range(n) if labels[k] == c))
                        for c in set(labels)))


def _empirical(labels_samples, n):
    c = Counter(_partition_key(s, n) for s in labels_samples)
    tot = sum(c.values())
    return {k: v / tot for k, v in c.items()}


def _enum_map(ev, prior_kind="microcluster", prior_params=None):
    return {tuple(sorted(part)): p
            for part, p in enumerate_posterior(ev, prior_kind, prior_params or {})}


def _worst_gap(ev, out, n):
    exact = _enum_map(ev)
    emp = _empirical(out["labels_samples"], n)
    keys = set(exact) | set(emp)
    return max(abs(exact.get(k, 0.0) - emp.get(k, 0.0)) for k in keys)


def test_split_merge_recovers_two_clear_groups():
    # Two axes strongly separate {0,1} from {2,3}
    cat = [["A", "A"], ["A", "A"], ["B", "B"], ["B", "B"]]
    bases = [{"A": 0.5, "B": 0.5}, {"A": 0.5, "B": 0.5}]
    ev = Evidence(n=4, cat_vals=cat, bases=bases, conc=0.3, link={}, cannot=set(), beta=0.0)
    out = sample(ev, n_iter=3000, burn=1000, seed=0)
    # The MAP {0,1},{2,3} carries ~0.84 of the exact posterior, so a single draw is a poor
    # target; assert the empirical MODE recovers the two clear groups (matches enumeration).
    mode = Counter(_partition_key(s, 4) for s in out["labels_samples"]).most_common(1)[0][0]
    assert mode == ((0, 1), (2, 3))


def test_sample_respects_cannot_link_throughout():
    cat = [["A"], ["A"]]
    ev = Evidence(n=2, cat_vals=cat, bases=[{"A": 1.0}], conc=1.0,
                  link={}, cannot={frozenset({0, 1})}, beta=0.0)
    out = sample(ev, n_iter=500, burn=100, seed=2)
    assert all(s[0] != s[1] for s in out["labels_samples"])


def test_run_chains_returns_one_per_init():
    cat = [["A"], ["B"]]
    ev = Evidence(n=2, cat_vals=cat, bases=[{"A": 0.5, "B": 0.5}], conc=1.0,
                  link={}, cannot=set(), beta=0.0)
    chains = run_chains(ev, inits=[[0, 1], [0, 0]], n_iter=200, burn=50)
    assert len(chains) == 2


def test_split_merge_move_preserves_validity_and_labeling():
    # Mechanics: a single move returns a canonically-relabeled valid partition and never
    # co-clusters a cannot-link pair.
    cat = [["A"], ["A"], ["B"]]
    ev = Evidence(n=3, cat_vals=cat, bases=[{"A": 0.5, "B": 0.5}], conc=1.0,
                  link={}, cannot={frozenset({0, 1})}, beta=0.0)
    rng = random.Random(7)
    labels = [0, 1, 2]
    for _ in range(500):
        labels = split_merge_move(labels, ev, rng, "microcluster", {})
        assert labels[0] != labels[1]                       # cannot-link never violated
        assert set(labels) == set(range(len(set(labels))))  # canonical 0..k-1 relabeling
        assert log_posterior(labels, ev, "microcluster", {}) != -math.inf


def test_sample_stationary_matches_enumeration():
    # HARD CORRECTNESS GATE: the full interleaved sampler must reproduce the exact posterior.
    # Config A: non-trivial categorical signal.
    cat_a = [["A"], ["A"], ["B"]]
    ev_a = Evidence(n=3, cat_vals=cat_a, bases=[{"A": 0.5, "B": 0.5}], conc=1.0,
                    link={}, cannot=set(), beta=0.0)
    out_a = sample(ev_a, n_iter=30000, burn=3000, seed=0)
    worst_a = _worst_gap(ev_a, out_a, 3)
    assert worst_a < 0.03, f"config A worst gap {worst_a}"

    # Config B: cannot-link between two otherwise-identical nodes.
    cat_b = [["A"], ["A"], ["A"]]
    ev_b = Evidence(n=3, cat_vals=cat_b, bases=[{"A": 1.0}], conc=1.0,
                    link={}, cannot={frozenset({0, 1})}, beta=0.0)
    out_b = sample(ev_b, n_iter=30000, burn=3000, seed=1)
    worst_b = _worst_gap(ev_b, out_b, 3)
    assert worst_b < 0.03, f"config B worst gap {worst_b}"
