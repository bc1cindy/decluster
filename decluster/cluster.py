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

def cluster_fused(nodes, combiner, refuse_below=-2.0, link_above=4.0):
    """like cluster_fingerprint_aware, but adds the amount weight to the fingerprint score
    (linear combination). refused = (a,b,t,fp,amt,total)."""
    uf = UF(nodes); refused = []; linked = []
    for a, b, t in _cospent_pairs(nodes):
        fp = combiner.score(fetch_tx(a), fetch_tx(b))
        amt = amount_refuse_weight(t, a, b)
        total = fp + amt
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
