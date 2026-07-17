"""Bayesian (Gibbs) record linkage over the per-axis agree/disagree likelihood — the classic per-field
Fellegi-Sunter form with m_j given a Beta prior and u_j fixed at the measured collision. F-S is the
plug-in (point-m) special case. Offline, deterministic. Consumes the fs_em.agree_matrix (A, mask, u)
shape; see results/RESULTS-bayes-vs-fs.md. NOTE: this is the axis-level F-S, not combiner.fs_score
(which is value-specific)."""
import math
import random

_EPS = 1e-6


def _clamp(x, lo=_EPS, hi=1 - _EPS):
    return lo if x < lo else hi if x > hi else x


def pair_probs(A, mask, m, u, lam):
    """Per-pair P(match) under the per-field naive-Bayes likelihood: log-LR = Σ over active axes of
    a·log(m/u) + (1−a)·log((1−m)/(1−u)); P = λ·LR / (λ·LR + (1−λ)). Axis-level F-S, not fs_score."""
    m = [_clamp(v) for v in m]
    u = [_clamp(v) for v in u]
    k = len(u)
    out = []
    for row, mk in zip(A, mask):
        ll = 0.0
        for j in range(k):
            if not mk[j]:
                continue
            if row[j]:
                ll += math.log(m[j]) - math.log(u[j])
            else:
                ll += math.log(1 - m[j]) - math.log(1 - u[j])
        top = math.log(lam) + ll
        bot = math.log(1 - lam)
        mx = top if top > bot else bot
        et, eb = math.exp(top - mx), math.exp(bot - mx)
        out.append(et / (et + eb))
    return out


def gibbs_fit(A, mask, u, alpha=8.5, beta=1.5, n_samples=2000, burn=500, seed=0):
    """Gibbs over (z, m): Beta(alpha,beta) prior on each m_j, u fixed. Match = higher-agreement class
    (prior mean ~0.85, high-agreement z init) to prevent label-switching. Deterministic under seed."""
    rng = random.Random(seed)
    n, k = len(A), len(u)
    u = [_clamp(v) for v in u]
    z = []
    for row, mk in zip(A, mask):
        active = [row[j] for j in range(k) if mk[j]]
        z.append(1 if active and sum(active) * 2 >= len(active) else 0)
    m = [alpha / (alpha + beta)] * k
    lam = 0.5
    m_samples, lam_samples = [], []
    p_accum = [0.0] * n
    kept = 0
    for it in range(n_samples):
        for j in range(k):
            ag = de = 0
            for i in range(n):
                if mask[i][j] and z[i]:
                    if A[i][j]:
                        ag += 1
                    else:
                        de += 1
            m[j] = _clamp(rng.betavariate(alpha + ag, beta + de))
        sz = sum(z)
        lam = _clamp(rng.betavariate(1 + sz, 1 + n - sz))
        pm = pair_probs(A, mask, m, u, lam)
        for i in range(n):
            z[i] = 1 if rng.random() < pm[i] else 0
        if it >= burn:
            m_samples.append(list(m))
            lam_samples.append(lam)
            for i in range(n):
                p_accum[i] += pm[i]
            kept += 1
    m_mean = [sum(s[j] for s in m_samples) / kept for j in range(k)]
    m_ci = []
    for j in range(k):
        col = sorted(s[j] for s in m_samples)
        m_ci.append((col[int(0.025 * (kept - 1))], col[int(0.975 * (kept - 1))]))
    return {"m_mean": m_mean, "m_ci": m_ci, "lam_mean": sum(lam_samples) / kept,
            "p_match": [p_accum[i] / kept for i in range(n)], "m_samples": m_samples}


def ece(probs, labels, bins=10):
    """Expected calibration error: Σ_bin (|bin| / n) · |conf − acc| over equal-width bins."""
    n = len(probs)
    if n == 0:
        return 0.0
    total = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i in range(n)
               if probs[i] >= lo and (probs[i] < hi or (b == bins - 1 and probs[i] <= hi))]
        if not idx:
            continue
        conf = sum(probs[i] for i in idx) / len(idx)
        acc = sum(labels[i] for i in idx) / len(idx)
        total += (len(idx) / n) * abs(conf - acc)
    return total
