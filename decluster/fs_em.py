"""Unsupervised EM for the per-axis Fellegi-Sunter m (u fixed at the measured collision), plus a
supervised reuse-label oracle. Offline, deterministic. See combiner.fs_score for the scoring kernel and
results/RESULTS-em-m.md for the reading."""
import math

_EPS = 1e-6


def _clamp(x, lo=_EPS, hi=1 - _EPS):
    return lo if x < lo else hi if x > hi else x


def agree_matrix(pairs, axes):
    """Per pair, the agree-indicator vector over `axes` (the LibraryScorer axis list
    [(name, fn, p, collision, abstain)]) plus an active-mask (False where the axis abstains).
    Returns (A, mask, names, u): A/mask are n_pairs x n_axes; u = per-axis collision (the fixed u)."""
    names = [name for name, *_ in axes]
    u = [collision for _, _, _, collision, _ in axes]
    A, mask = [], []
    for txA, txB in pairs:
        arow, mrow = [], []
        for _, fn, _, _, abstain in axes:
            va, vb = fn(txA), fn(txB)
            if abstain(va, vb):
                arow.append(0); mrow.append(False)
            else:
                arow.append(1 if va == vb else 0); mrow.append(True)
        A.append(arow); mask.append(mrow)
    return A, mask, names, u


def em_fit(A, mask, u, max_iter=100, tol=1e-6):
    """Fit per-axis m by EM over the unlabeled pair mixture; u fixed. A/mask: n_pairs x n_axes agree
    indicators / active mask. Returns {m, lam, r, n_iter, loglik}. Deterministic: init m=0.9, lam=0.5."""
    n = len(A)
    k = len(u)
    u = [_clamp(uj) for uj in u]
    m = [0.9] * k
    lam = 0.5
    r = [0.0] * n
    loglik = []
    n_iter = 0
    for it in range(1, max_iter + 1):
        n_iter = it
        mc = [_clamp(mj) for mj in m]
        ll = 0.0
        # E-step: per-pair posterior match prob r via the per-field F-S likelihood (same formula as
        # fs_bayes.pair_probs) fused here with the incomplete-data log-likelihood ll in one pass.
        for i in range(n):
            lM = lU = 0.0
            for j in range(k):
                if not mask[i][j]:
                    continue
                if A[i][j]:
                    lM += math.log(mc[j]); lU += math.log(u[j])
                else:
                    lM += math.log(1 - mc[j]); lU += math.log(1 - u[j])
            top = math.log(lam) + lM
            bot = math.log(1 - lam) + lU
            mx = top if top > bot else bot
            et, eb = math.exp(top - mx), math.exp(bot - mx)
            r[i] = et / (et + eb)
            ll += mx + math.log(et + eb)
        loglik.append(ll)
        lam = _clamp(sum(r) / n) if n else 0.5
        newm = list(m)
        for j in range(k):
            num = den = 0.0
            for i in range(n):
                if mask[i][j]:
                    num += r[i] * A[i][j]; den += r[i]
            if den > 1e-12:
                newm[j] = _clamp(num / den)
        m = newm
        if len(loglik) >= 2 and abs(loglik[-1] - loglik[-2]) < tol:
            break
    return {"m": m, "lam": lam, "r": r, "n_iter": n_iter, "loglik": loglik}


def oracle_m(A, mask, labels):
    """Supervised per-axis m: agree-rate on each axis among the true positives (label==1), over pairs
    where the axis is active. Returns a per-axis list; an axis with no active positive -> None."""
    k = len(A[0]) if A else 0
    out = []
    for j in range(k):
        num = den = 0
        for i in range(len(A)):
            if labels[i] == 1 and mask[i][j]:
                num += A[i][j]; den += 1
        out.append(num / den if den else None)
    return out
