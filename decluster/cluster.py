"""Layer 4 — graph-level clustering: single-heuristic union-find (common-input-ownership)
collapse vs. fingerprint-aware clustering."""
from .fetch import fetch_tx
from .subtransaction import subtransactions, partition_signal

class UF:
    def __init__(self, items): self.p = {x: x for x in items}
    def find(self, x):
        while self.p[x] != x: self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def union(self, a, b): self.p[self.find(a)] = self.find(b)
    def group(self, x):
        r = self.find(x); return [y for y in self.p if self.find(y) == r]
    def groups(self):
        g = {}
        for x in self.p: g.setdefault(self.find(x), []).append(x)
        return list(g.values())

def _cospent_pairs(nodes):
    """common-input-ownership: coins co-spent in one tx -> same owner. A node is the txid
    that funded a coin; if tx T spends coins funded by F1,F2..., F1,F2 get a same-owner edge."""
    pairs = []
    for t in nodes:
        funders = [vin["txid"] for vin in fetch_tx(t)["vin"] if vin["txid"] in nodes]
        for i in range(len(funders)):
            for j in range(i+1, len(funders)):
                pairs.append((funders[i], funders[j], t))
    return pairs

def cluster_naive(nodes):
    """pure union-find over common-input-ownership (the BlockSci heuristic)."""
    uf = UF(nodes)
    for a, b, _ in _cospent_pairs(nodes): uf.union(a, b)
    return uf.groups()

def cluster_fingerprint_aware(nodes, combiner, refuse_below=-2.0, link_above=4.0):
    """(1) REFUSES a co-spent merge when the fingerprint says 'different wallets' (avoids
    merged transaction collapse); (2) ADDS links common-input misses when two coins share a rare
    fingerprint (score >= link_above)."""
    uf = UF(nodes); refused = []; linked = []
    for a, b, t in _cospent_pairs(nodes):
        if combiner.score(fetch_tx(a), fetch_tx(b)) < refuse_below:
            refused.append((a, b, t, combiner.score(fetch_tx(a), fetch_tx(b)))); continue
        uf.union(a, b)
    node_list = list(nodes)
    for i in range(len(node_list)):
        for j in range(i+1, len(node_list)):
            a, b = node_list[i], node_list[j]
            sc = combiner.score(fetch_tx(a), fetch_tx(b))
            if sc >= link_above:
                uf.union(a, b); linked.append((a, b, sc))
    return uf.groups(), refused, linked

def _norm(t):
    """mempool.space tx -> shape subtransaction expects (prevout.value present)."""
    return {"txid": t["txid"],
            "vin": [{"txid": v["txid"], "prevout": {"value": v["prevout"]["value"]}} for v in t["vin"]],
            "vout": [{"value": o["value"]} for o in t["vout"]]}

def amount_refuse_weight(t, a, b):
    """structural amount weight (<=0): if t's best partition splits inputs a,b (different
    owners), returns -(roundness margin); 0 if out of scope / no split. A prior, not
    calibrated bits."""
    tx = _norm(fetch_tx(t))
    ins = [v["txid"] for v in tx["vin"]]
    if set(ins) != {a, b}:
        return 0.0
    ranked, _amb = subtransactions(tx)
    if not ranked:
        return 0.0
    sig = partition_signal(tx)
    splits = any({x, y} == {a, b} for (x, y) in sig["refuse"])
    if not splits:
        return 0.0
    margin = ranked[0][1] - (ranked[1][1] if len(ranked) > 1 else 0)  # winner - runner-up roundness
    return -float(margin)

def counterparty_bits(neigh):
    """rarity of each counterparty as node-frequency bits: `-log2(share of nodes touching
    it)`. A hub (an exchange everyone touches) -> few bits; a private address -> many.
    Calibrated from the graph itself, so a shared counterparty is weighted like a fingerprint
    value. `neigh`: node -> counterparty set."""
    import math
    touch = {}
    for a in neigh:
        for c in neigh[a]:
            touch[c] = touch.get(c, 0) + 1
    n = len(neigh) or 1
    return {c: -math.log2(f / n) for c, f in touch.items()}

def topology_weight(a, b, neigh, cbits=None, disjoint_bits=-1.65, share_cap=12.0):
    """graph-topology weight (signed) from counterparty neighbourhoods, as a Fellegi-Sunter
    quasi-identifier. MATCH (shared counterparties) -> same-owner bits, rarity-weighted via
    `cbits` (a rare shared address is strong, a hub ~0). MISMATCH (disjoint) -> `disjoint_bits`,
    calibrated *weak*: on a real slice P(disjoint|same)=0.32 vs P(disjoint|diff)=1.00 ->
    log2 ratio ~= -1.65, so a SINGLE disjoint pair barely moves the score and cannot by itself
    overcome a fingerprint match. The refusal the collaborator describes ('enough
    distinguishing relationships') is the ACCUMULATION of these across a whole cluster — an
    N-S cluster-level computation, not this per-pair term (paper §10). 0 when either side has
    too little graph to judge."""
    na, nb = neigh.get(a, set()), neigh.get(b, set())
    if not na or not nb:
        return 0.0
    common = na & nb
    if common:
        if cbits is not None:
            return min(sum(cbits.get(c, 0.0) for c in common), share_cap)   # calibrated bits
        return 1.5 * min(len(common), 4)                                    # prototype bonus
    return disjoint_bits                                   # disjoint: calibrated but weak per-pair

def _agg(members, neigh):
    s = set()
    for x in members:
        s |= neigh.get(x, set())
    return s

def _overlap_bits(common, cbits, share_cap):
    if not common:
        return 0.0
    if cbits is not None:
        return min(sum(cbits.get(c, 0.0) for c in common), share_cap)
    return 1.5 * min(len(common), 4)

DISJOINT_BITS = -8.1   # calibrated ~-8: same-owner clusters never disjoint (0/272), diff owners do (99.7%)

def cluster_topology_weight(members_a, members_b, neigh, cbits=None, disjoint_bits=DISJOINT_BITS, share_cap=12.0, tau=0.0):
    """cluster-level topology as a Fellegi-Sunter quasi-identifier: aggregate two clusters'
    counterparty neighbourhoods and weight the overlap by GLOBAL rarity (`cbits`, `-log2(share)`) —
    a shared rare counterparty is strong same-owner evidence, a common hub ~0 bits. The overlap-bit
    magnitude *is* the distinctiveness; on a real slice it separates same-owner (mean 11.7 bits) from
    different-owner (mean 0.004; 99.97% share nothing) at AUC 1.00. `tau` (bits) is the
    distinctiveness threshold: an overlap below `tau` — disjoint, or sharing only non-distinctive
    hubs — is treated as disjoint (`disjoint_bits ~ -8`), refusing the merge; `>= tau` corroborates
    same owner. This is global (no candidate window), so it is field-independent and a universal hub
    (0 bits < tau) is correctly refused. `tau=0` keeps any shared counterparty (legacy). 0 when
    either side has too little graph to judge."""
    na, nb = _agg(members_a, neigh), _agg(members_b, neigh)
    if not na or not nb:
        return 0.0
    common = na & nb
    if not common:
        return disjoint_bits
    bits = _overlap_bits(common, cbits, share_cap)
    return bits if bits >= tau else disjoint_bits

def calibrate_topo_tau(sample, seed=0):
    """Discriminative calibration of the distinctiveness threshold `tau` on a real slice
    (graph_deanon.build payment graph). Compares the rarity-weighted counterparty-overlap bits of
    same-owner cluster pairs (split-half) vs different-owner pairs. A `tau` between the two means
    separates distinctive overlap (same-owner evidence) from non-distinctive/hub-only overlap
    (treated as disjoint). Returns (n_clusters, same_mean, cross_mean, auc); AUC -> 1 means the
    overlap-bit threshold cleanly separates owners, so it genuinely controls the false positive."""
    import random
    from .graph_deanon import build, _clusters, auc as _auc
    uf, _neigh_full, neigh_pay, _cospent = build(sample)
    groups = [m for m in _clusters(uf, neigh_pay).values() if len(m) >= 2]
    cbits = counterparty_bits(neigh_pay)
    rng = random.Random(seed)
    def ov(A, B):
        na, nb = _agg(A, neigh_pay), _agg(B, neigh_pay)
        return _overlap_bits(na & nb, cbits, 12.0) if na and nb else None
    same, cross = [], []
    for m in groups:
        h = len(m) // 2
        v = ov(m[:h], m[h:])
        if v is not None:
            same.append(v)
    for _ in range(min(3000, len(groups) * len(groups)) if len(groups) >= 2 else 0):
        v = ov(*rng.sample(groups, 2))
        if v is not None:
            cross.append(v)
    if not same or not cross:
        return (len(groups), None, None, None)
    return (len(groups), sum(same) / len(same), sum(cross) / len(cross), _auc(same, cross, seed))

def cluster_fused(nodes, combiner, refuse_below=-2.0, link_above=4.0, neigh=None, topo_tau=1.0):
    """like cluster_fingerprint_aware, but adds the amount weight and (when `neigh` is given) a
    CLUSTER-LEVEL graph-topology weight: co-spent merges are evaluated confident-first (shared
    counterparties before disjoint), and each is scored by the rarity-weighted counterparty overlap
    of the two *current* clusters (`cluster_topology_weight`, distinctiveness threshold `topo_tau`
    bits). An overlap below `topo_tau` — disjoint, or sharing only non-distinctive hubs — is treated
    as disjoint (~-8 bits), refusing a same-software payjoin. refused = (a,b,t,fp,amt,total)."""
    uf = UF(nodes); refused = []; linked = []
    cbits = counterparty_bits(neigh) if neigh else None
    pairs = _cospent_pairs(nodes)
    if neigh:                          # confident (shared) merges first, ambiguous (disjoint) last
        pairs = sorted(pairs, key=lambda p: -topology_weight(p[0], p[1], neigh, cbits))
    for a, b, t in pairs:
        fp = combiner.score(fetch_tx(a), fetch_tx(b))
        amt = amount_refuse_weight(t, a, b)
        top = cluster_topology_weight(uf.group(a), uf.group(b), neigh, cbits, tau=topo_tau) if neigh else 0.0
        total = fp + amt + top
        if total < refuse_below:
            refused.append((a, b, t, fp, amt, total)); continue
        uf.union(a, b)
    node_list = list(nodes)
    for i in range(len(node_list)):
        for j in range(i + 1, len(node_list)):
            a, b = node_list[i], node_list[j]
            sc = combiner.score(fetch_tx(a), fetch_tx(b))
            if sc >= link_above:
                uf.union(a, b); linked.append((a, b, sc))
    return uf.groups(), refused, linked
