"""Unnormalized log-posterior over partitions of a bounded coin slice (super-nodes indexed
0..n-1). Hybrid likelihood: generative Dirichlet-multinomial for categorical fingerprint axes
(the partition lift of fs_bayes's Beta-Bernoulli m/u), a pairwise N-S similarity factor for
sparse provenance/topology, and a hard cannot-link mask for the amount refuse-only channel.
Pure function of (partition, evidence). Every fused number is a weight-of-evidence lower bound,
not a privacy score. Offline, stdlib only."""
import math
from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from .partition_prior import log_prior as _log_prior

_EPS = 1e-9


@dataclass(frozen=True)
class Evidence:
    n: int
    cat_vals: list        # n x n_axes: super-node -> [value per axis]
    bases: list           # n_axes: {value: population share}
    conc: float           # Dirichlet concentration (base measure = conc * share)
    link: dict            # {(i,j): float} i<j  — N-S similarity (Task 3)
    cannot: set           # {frozenset({i,j})}  — amount cannot-links (Task 3)
    beta: float           # N-S factor scale (Task 3)


def _log_dirmult(counts, base, conc):
    """log Dirichlet-multinomial marginal of a value multiset. base: {value: share} (sums ~1);
    pseudo-counts gamma_v = conc * share_v, so sum(gamma) = conc."""
    total = sum(counts.values())
    lg = math.lgamma(conc) - math.lgamma(total + conc)
    for v, nv in counts.items():
        g = conc * max(base.get(v, _EPS), _EPS)
        lg += math.lgamma(nv + g) - math.lgamma(g)
    return lg


def categorical_loglik(members, ev):
    """Sum over axes of the Dirichlet-multinomial marginal log-likelihood of the members'
    values on that axis. For merge assessment (Bayesian merge ratio), compute merge gain as
    categorical_loglik([i,j]) - categorical_loglik([i]) - categorical_loglik([j]); rarity
    signal (stronger evidence for rare shared values) appears in that gain, not raw value."""
    out = 0.0
    for j in range(len(ev.bases)):
        base = ev.bases[j]
        counts = Counter(ev.cat_vals[i][j] for i in members
                         if ev.cat_vals[i][j] in base)   # abstain: unmeasured value is not evidence
        if counts:
            out += _log_dirmult(counts, base, ev.conc)
    return out


def groups(labels):
    """Member lists per cluster id."""
    out = {}
    for i, c in enumerate(labels):
        out.setdefault(c, []).append(i)
    return list(out.values())


def cluster_loglik(members, ev):
    """Categorical Dirichlet-multinomial + beta-scaled within-cluster N-S similarity."""
    ll = categorical_loglik(members, ev)
    if ev.beta and len(members) > 1:
        s = 0.0
        for i, j in combinations(sorted(members), 2):
            s += ev.link.get((i, j), 0.0)
        ll += ev.beta * s
    return ll


def _violates_cannot(members, cannot):
    if not cannot:
        return False
    mset = set(members)
    for pair in cannot:
        if pair <= mset:
            return True
    return False


def log_posterior(labels, ev, prior_kind="microcluster", prior_params=None):
    """Unnormalized log-posterior: sum of cluster log-likelihoods + partition prior.
    -inf if any amount cannot-link pair is co-clustered (refuse-only hard mask)."""
    gs = groups(labels)
    total = 0.0
    for members in gs:
        if _violates_cannot(members, ev.cannot):
            return -math.inf
        total += cluster_loglik(members, ev)
    total += _log_prior([len(m) for m in gs], kind=prior_kind, **(prior_params or {}))
    return total


def contract_cospend(txs):
    """Group tx indices into co-spend super-nodes by shared input addresses (union-find)."""
    from .unionfind import UF
    uf = UF()
    addr_of = []
    for tx in txs:
        addrs = [v.get("prevout", {}).get("scriptpubkey_address")
                 for v in tx.get("vin", [])]
        addrs = [a for a in addrs if a]
        addr_of.append(addrs)
        for a in addrs[1:]:
            uf.union(addrs[0], a)
    groups_by_root = {}
    for idx, addrs in enumerate(addr_of):
        root = uf.find(addrs[0]) if addrs else ("__solo__", idx)
        groups_by_root.setdefault(root, []).append(idx)
    return list(groups_by_root.values())


def build_evidence(supernodes, *, conc=1.0, beta=1.0, link_fn=None, cannot_pairs=None):
    """Assemble an Evidence from super-nodes ({"txs": [...], "sig": {ancestor: mass}}). A
    super-node's categorical value per axis comes from its representative (first) tx; co-spent
    txs share the wallet, so the fingerprint is shared by construction."""
    from .ancestry import provenance_link
    from .fingerprint_validate import LibraryScorer
    axes = LibraryScorer().axes                      # [(name, fn, p, collision, abstain), ...]
    bases = [dict(p) for _, _, p, *_ in axes]
    link_fn = link_fn or provenance_link
    cat_vals = []
    sigs = []
    for sn in supernodes:
        rep = sn["txs"][0]
        vals = []
        for _, fn, *_ in axes:
            try:
                val = fn(rep)
            except (KeyError, IndexError, TypeError):
                val = None            # incomplete tx data -> unmeasured; categorical_loglik abstains
            vals.append(val)
        cat_vals.append(vals)
        sigs.append(sn.get("sig", {}))
    link = {}
    n = len(supernodes)
    for i in range(n):
        for j in range(i + 1, n):
            w = link_fn(sigs[i], sigs[j])
            if w > 0.0:
                link[(i, j)] = w
    cannot = set(cannot_pairs or set())
    return Evidence(n=n, cat_vals=cat_vals, bases=bases, conc=conc,
                     link=link, cannot=cannot, beta=beta)
