"""Bayesian (Gibbs) record linkage: pair_probs kernel, gibbs_fit posterior, ece calibration."""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _synth(n, m_true, u_true, lam, seed):
    rng = random.Random(seed)
    k = len(m_true)
    A, mask, labels = [], [], []
    for _ in range(n):
        match = rng.random() < lam
        labels.append(1 if match else 0)
        probs = m_true if match else u_true
        A.append([1 if rng.random() < probs[j] else 0 for j in range(k)])
        mask.append([True] * k)
    return A, mask, labels


def test_pair_probs_matches_closed_form_lr():
    from decluster.fs_bayes import pair_probs
    # one pair, 2 axes both agree; m=[0.9,0.8] u=[0.3,0.2] lam=0.5
    A, mask = [[1, 1]], [[True, True]]
    m, u = [0.9, 0.8], [0.3, 0.2]
    lr = (0.9 / 0.3) * (0.8 / 0.2)                      # both agree
    expected = lr * 0.5 / (lr * 0.5 + 0.5)              # = lr/(lr+1)
    assert abs(pair_probs(A, mask, m, u, 0.5)[0] - expected) < 1e-9


def test_pair_probs_abstain_axis_contributes_nothing():
    from decluster.fs_bayes import pair_probs
    A, mask = [[1, 0]], [[True, False]]                 # axis 2 inactive
    m, u = [0.9, 0.8], [0.3, 0.2]
    lr = 0.9 / 0.3                                       # only axis 1
    assert abs(pair_probs(A, mask, m, u, 0.5)[0] - lr / (lr + 1)) < 1e-9


def test_gibbs_recovers_m_and_ci_covers_truth():
    from decluster.fs_bayes import gibbs_fit
    m_true, u_true, lam = [0.95, 0.80, 0.60], [0.30, 0.20, 0.50], 0.5
    A, mask, _ = _synth(3000, m_true, u_true, lam, seed=1)
    out = gibbs_fit(A, mask, u_true, seed=1)
    for j in range(3):
        assert abs(out["m_mean"][j] - m_true[j]) < 0.07
        lo, hi = out["m_ci"][j]
        assert lo <= m_true[j] <= hi


def test_gibbs_no_label_switch_m_above_u():
    from decluster.fs_bayes import gibbs_fit
    A, mask, _ = _synth(2000, [0.9, 0.85], [0.3, 0.4], 0.5, seed=2)
    out = gibbs_fit(A, mask, [0.3, 0.4], seed=2)
    assert out["m_mean"][0] > 0.3 and out["m_mean"][1] > 0.4


def test_gibbs_posterior_contracts_with_data():
    from decluster.fs_bayes import gibbs_fit
    small = gibbs_fit(*_synth(200, [0.9], [0.3], 0.5, seed=3)[:2], u=[0.3], seed=3)
    big = gibbs_fit(*_synth(5000, [0.9], [0.3], 0.5, seed=4)[:2], u=[0.3], seed=4)
    w_small = small["m_ci"][0][1] - small["m_ci"][0][0]
    w_big = big["m_ci"][0][1] - big["m_ci"][0][0]
    assert w_big < w_small


def test_gibbs_deterministic():
    from decluster.fs_bayes import gibbs_fit
    A, mask, _ = _synth(500, [0.9], [0.3], 0.5, seed=5)
    a = gibbs_fit(A, mask, [0.3], seed=7)
    b = gibbs_fit(A, mask, [0.3], seed=7)
    assert a["m_mean"] == b["m_mean"] and a["p_match"] == b["p_match"]


def test_ece_perfect_and_miscalibrated():
    from decluster.fs_bayes import ece
    # perfectly calibrated: in-bin mean prob == in-bin label rate
    assert ece([0.5, 0.5, 0.5, 0.5], [1, 1, 0, 0], bins=10) < 1e-9
    # all predict 0.9 but half are 0 -> |0.9 - 0.5| = 0.4
    assert abs(ece([0.9, 0.9, 0.9, 0.9], [1, 1, 0, 0], bins=10) - 0.4) < 1e-9
