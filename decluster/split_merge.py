"""Split-merge MCMC over partitions of co-spend super-nodes (indices 0..n-1). A single-node
restricted-Gibbs sweep plus a Jain-Neal split-merge move (Task 6), driven multi-chain (Task 6).
Deterministic under an explicit RNG. Offline, stdlib only. Every readout is a weight-of-evidence
lower bound, not a privacy score."""
import math
import random
from .partition_model import log_posterior


def _relabel(labels):
    remap, out, nxt = {}, [], 0
    for c in labels:
        if c not in remap:
            remap[c] = nxt
            nxt += 1
        out.append(remap[c])
    return out


def gibbs_sweep(labels, ev, rng, prior_kind, prior_params):
    """Reassign each super-node to an existing cluster (of the other nodes) or a fresh
    singleton, sampled proportional to the full log-posterior. Node i is removed from its
    cluster before enumerating candidates (Neal restricted-Gibbs). Respects cannot-links."""
    labels = list(labels)
    for i in range(ev.n):
        others = set(labels[k] for k in range(ev.n) if k != i)
        fresh = (max(others) + 1) if others else 0
        candidates = sorted(others) + [fresh]  # other nodes' clusters + one fresh singleton
        logps = []
        for c in candidates:
            trial = list(labels)
            trial[i] = c
            logps.append(log_posterior(trial, ev, prior_kind, prior_params))
        mx = max(logps)
        if mx == -math.inf:
            continue
        weights = [math.exp(lp - mx) if lp != -math.inf else 0.0 for lp in logps]
        tot = sum(weights)
        r = rng.random() * tot
        acc = 0.0
        for c, w in zip(candidates, weights):
            acc += w
            if r <= acc:
                labels[i] = c
                break
    return _relabel(labels)


def _set_partitions(items):
    if len(items) == 1:
        yield [items]
        return
    first, rest = items[0], items[1:]
    for smaller in _set_partitions(rest):
        for k in range(len(smaller)):
            yield smaller[:k] + [[first] + smaller[k]] + smaller[k + 1:]
        yield [[first]] + smaller


def enumerate_posterior(ev, prior_kind="microcluster", prior_params=None):
    """All set partitions of 0..n-1 with normalized posterior probability (small n only)."""
    assert ev.n <= 6, "enumeration is exponential; use only for small validation cases"
    parts, logps = [], []
    for part in _set_partitions(list(range(ev.n))):
        labels = [0] * ev.n
        for cid, block in enumerate(part):
            for i in block:
                labels[i] = cid
        parts.append(tuple(tuple(sorted(b)) for b in part))
        logps.append(log_posterior(labels, ev, prior_kind, prior_params or {}))
    mx = max(lp for lp in logps if lp != -math.inf)
    ws = [math.exp(lp - mx) if lp != -math.inf else 0.0 for lp in logps]
    tot = sum(ws)
    return [(p, w / tot) for p, w in zip(parts, ws)]


def _restricted_scan(work, order, ca, cb, ev, prior_kind, pp, rng, sample, target):
    """One restricted Gibbs scan over `order` between clusters `ca`/`cb`, mutating `work`.
    Each node k is (re)assigned by its full-posterior conditional restricted to the two
    clusters. If `sample`, draw the assignment; else force it to `target[k]`. Returns the
    log-product of the chosen/forced conditional probabilities, or None if some required
    assignment is forbidden by a cannot-link (conditional probability 0)."""
    log_q = 0.0
    for k in order:
        t = list(work)
        t[k] = ca
        la = log_posterior(t, ev, prior_kind, pp)
        t[k] = cb
        lb = log_posterior(t, ev, prior_kind, pp)
        if la == -math.inf and lb == -math.inf:
            return None
        mx = max(la, lb)
        wa = math.exp(la - mx) if la != -math.inf else 0.0
        wb = math.exp(lb - mx) if lb != -math.inf else 0.0
        pa = wa / (wa + wb)
        choose_a = (rng.random() < pa) if sample else (target[k] == ca)
        work[k] = ca if choose_a else cb
        p = pa if choose_a else 1.0 - pa
        if p <= 0.0:
            return None
        log_q += math.log(p)
    return log_q


def _launch(work, S, ca, cb, ev, prior_kind, pp, rng, order, launch_scans):
    """Seed a random restricted split (i,j already anchored) and decorrelate it with
    `launch_scans` restricted Gibbs scans. Returns False if the region is over-constrained."""
    for k in S:
        work[k] = ca if rng.random() < 0.5 else cb
    for _ in range(launch_scans):
        rng.shuffle(order)
        if _restricted_scan(work, order, ca, cb, ev, prior_kind, pp, rng, True, None) is None:
            return False
    return True


def split_merge_move(labels, ev, rng, prior_kind, prior_params, launch_scans=1):
    """One exact Jain-Neal (2004) restricted-Gibbs split-merge Metropolis-Hastings step.
    Picks two super-nodes; if same cluster proposes a SPLIT via a launch + final restricted
    Gibbs scan (proposal density = product of the final-scan conditionals, reverse merge is
    deterministic); if different proposes the deterministic MERGE (Hastings correction = the
    probability the reverse split would reconstruct the original). Cannot-link violations get
    conditional probability 0, so any fully-forbidden proposal is rejected."""
    pp = prior_params or {}
    if ev.n < 2:
        return _relabel(labels)
    i, j = rng.sample(range(ev.n), 2)
    labels = list(labels)
    ci, cj = labels[i], labels[j]
    cur_logp = log_posterior(labels, ev, prior_kind, pp)
    ca = max(labels) + 1
    cb = ca + 1

    if ci == cj:
        # SPLIT proposal: anchor i in A, j in B; launch, then one recorded final scan.
        S = [k for k in range(ev.n) if k not in (i, j) and labels[k] == ci]
        work = list(labels)
        work[i], work[j] = ca, cb
        order = list(S)
        if not _launch(work, S, ca, cb, ev, prior_kind, pp, rng, order, launch_scans):
            return _relabel(labels)
        rng.shuffle(order)
        log_q = _restricted_scan(work, order, ca, cb, ev, prior_kind, pp, rng, True, None)
        if log_q is None:
            return _relabel(labels)
        prop = work
        prop_logp = log_posterior(prop, ev, prior_kind, pp)
        # reverse merge is deterministic (q=1): accept min(1, exp(dlogp) / q_split)
        log_accept = prop_logp - cur_logp - log_q
    else:
        # MERGE proposal (deterministic): union cj into ci.
        prop = [ci if c == cj else c for c in labels]
        prop_logp = log_posterior(prop, ev, prior_kind, pp)
        if prop_logp == -math.inf:
            return _relabel(labels)
        # Hastings term: probability the reverse split reconstructs the original assignment.
        S = [k for k in range(ev.n) if k not in (i, j) and labels[k] in (ci, cj)]
        work = list(prop)
        work[i], work[j] = ca, cb
        order = list(S)
        if not _launch(work, S, ca, cb, ev, prior_kind, pp, rng, order, launch_scans):
            return _relabel(labels)
        target = {k: (ca if labels[k] == ci else cb) for k in S}
        rng.shuffle(order)
        log_q = _restricted_scan(work, order, ca, cb, ev, prior_kind, pp, rng, False, target)
        if log_q is None:
            return _relabel(labels)
        # accept min(1, exp(dlogp) * q_reverse-split)
        log_accept = prop_logp - cur_logp + log_q

    if log_accept >= 0.0 or rng.random() < math.exp(log_accept):
        return _relabel(prop)
    return _relabel(labels)


def sample(ev, *, n_iter=2000, burn=500, thin=1, seed=0,
           prior_kind="microcluster", prior_params=None, init=None):
    """Interleave one split-merge move and one Gibbs sweep per iteration; collect post-burn,
    thinned partition samples and their log-posterior trace. Deterministic under `seed`."""
    rng = random.Random(seed)
    pp = prior_params or {}
    labels = _relabel(init) if init is not None else list(range(ev.n))
    samples, trace = [], []
    for it in range(n_iter):
        labels = split_merge_move(labels, ev, rng, prior_kind, pp)
        labels = gibbs_sweep(labels, ev, rng, prior_kind, pp)
        if it >= burn and (it - burn) % thin == 0:
            samples.append(list(labels))
            trace.append(log_posterior(labels, ev, prior_kind, pp))
    return {"labels_samples": samples, "logp_trace": trace}


def run_chains(ev, inits, **kw):
    """One `sample` per init, with distinct seeds, for R-hat convergence checks."""
    base = kw.pop("seed", 0)
    return [sample(ev, seed=base + c, init=init, **kw) for c, init in enumerate(inits)]
