"""Partition the coin graph into views, then contract each into a pseudonym graph.

The cited framework's construction: coins are vertices, a clustering is a set of undirected
edges joining same-owner coins, and contracting those edges fuses each cluster into one
vertex whose residual edges are transfers of bitcoin. With a complete clustering that is a
user network; with the partial clustering an adversary actually holds it is a *pseudonym*
graph, and that is the object its matching algorithm consumes.

Two details the construction turns on:

  global clustering   the partition is applied to the coin graph, but the clustering that
                      annotates it is computed over the whole slice, then each part is
                      contracted with that same lookup. Clustering each part independently
                      would give the two views different vertex sets by construction.
  fold, don't stack   contraction yields a multigraph, one edge per transfer, but the
                      matching model wants a directed graph carrying one edge per ordered
                      pair with the parallel transfers collected into its attributes.

Vertex attributes are stored as raw counts alongside the view's own base rates, never as
bare shares: `RESULTS-attribute-drift.md` finds a median 54% of an axis value's variance
tracks epoch volume, a covariate that moves every vertex together, so an attribute has to
be read relative to its own view before it crosses the boundary.
"""
from collections import Counter, defaultdict

from .extractors import locktime_policy, x_fee_rate, x_input_order, x_version
from .monitor import is_coinjoin
from .unionfind import UF
from .change_gt import union_input_addrs

# The axes RESULTS-attribute-drift.md finds stable across a one-week gap. The high-drift
# axes (output types, feerate bucket, change position) are deliberately absent: at 4-8x the
# drift they do not survive the boundary they would be compared across.
AXES = {"version": x_version, "input_order": x_input_order,
        "locktime": locktime_policy, "fee_rate": x_fee_rate}


def _in_addrs(tx):
    return [a for a in (v.get("prevout", {}).get("scriptpubkey_address")
                        for v in tx.get("vin", [])) if a]


def _out_addrs(tx):
    return [(o.get("scriptpubkey_address"), o.get("value") or 0)
            for o in tx.get("vout", []) if o.get("scriptpubkey_address")]


def cluster_addresses(sample):
    """{address: cluster id} by common-input ownership over the WHOLE sample. The lookup is
    global on purpose: it is what lets a cluster keep one identity across the partition."""
    uf = UF()
    for tx, _ in sample:
        union_input_addrs(tx, uf)
    return {a: uf.find(a) for g in uf.groups() for a in g}


def partition_coins(sample, scheme="epoch", bounds=None, ambiguity=None, theta=1.0):
    """Split the sample into views, returning one list of sample indices per view.

    epoch             by block height, the trivial partition the framework names as its
                      example. `bounds` is [(lo, hi), ...]; without it the height range is
                      halved.
    coinjoin_boundary a coinjoin is where co-spending stops implying common ownership, so
                      it is a natural seam: transactions before and after form the views and
                      the coinjoins themselves are the boundary, in no view.
    ambiguity_cut     the framework's preferred scheme, the "opposite" of expander
                      decomposition: cut where the evidence is most ambiguous so each
                      component comes out sparser. `ambiguity(tx) -> float` supplies the
                      per-transaction evidence balance; transactions under `theta` are the
                      boundary and are excluded rather than assigned.

    A cut removes the boundary from the views and keeps the rest; it does not discard the
    vertices incident to it.
    """
    if scheme == "epoch":
        heights = [tx.get("height") or 0 for tx, _ in sample]
        if bounds is None:
            mid = (min(heights) + max(heights)) // 2
            bounds = [(min(heights), mid), (mid + 1, max(heights))]
        return [[i for i, h in enumerate(heights) if lo <= h <= hi] for lo, hi in bounds]

    if scheme == "coinjoin_boundary":
        seam = [i for i, (tx, _) in enumerate(sample) if is_coinjoin(tx)]
        cut = seam[len(seam) // 2] if seam else len(sample) // 2
        boundary = set(seam)
        return [[i for i in range(cut) if i not in boundary],
                [i for i in range(cut + 1, len(sample)) if i not in boundary]]

    if scheme == "ambiguity_cut":
        if ambiguity is None:
            raise ValueError("ambiguity_cut needs an `ambiguity` callable")
        keep = [i for i, (tx, _) in enumerate(sample) if abs(ambiguity(tx)) >= theta]
        half = len(keep) // 2
        return [keep[:half], keep[half:]]

    raise ValueError(f"unknown scheme: {scheme}")


class PseudonymGraph:
    """Contracted view. Vertices are clusters; `edges[(src, dst)]` is the single directed
    edge folding every transfer from src to dst, carrying how many there were and how much
    value moved. Value is kept because connectivity means a plausible flow, not merely a
    traceable one, so a matcher may discount an edge that only dust created."""

    def __init__(self):
        self.vertices = {}
        self.edges = {}
        self.base_rates = {axis: Counter() for axis in AXES}
        self.skipped = Counter()      # axis -> transactions it could not be read from
        self._out = defaultdict(set)
        self._in = defaultdict(set)

    def _vertex(self, vid):
        return self.vertices.setdefault(
            vid, {"coins": set(), "txs": 0, "self_transfers": 0,
                  "axes": {axis: Counter() for axis in AXES}})

    def neighbours(self, vid):
        return self._out[vid] | self._in[vid]

    def degree(self, vid):
        return len(self.neighbours(vid))

    def attribute(self, vid, axis):
        """The vertex's distribution over an axis, as a lift over this view's own base rate.
        1.0 means the vertex looks exactly like its view; the normalisation is what makes
        the value comparable to a vertex measured in another view."""
        counts = self.vertices[vid]["axes"][axis]
        total = sum(counts.values())
        base_total = sum(self.base_rates[axis].values())
        if not total or not base_total:
            return {}
        out = {}
        for value, n in counts.items():
            base = self.base_rates[axis].get(value, 0) / base_total
            out[value] = (n / total) / base if base else float("inf")
        return out


def contract(sample, indices=None, lookup=None, min_value=0):
    """Contract one view: fuse each cluster's coins into a vertex and fold the transfers
    between clusters into one attributed directed edge per ordered pair.

    An address absent from `lookup` is its own singleton pseudonym, which is the ordinary
    case under a partial clustering rather than an error. `min_value` drops transfers below
    a threshold, so a dust spray does not manufacture a relationship.

    `indices` selects from a materialised sample; passing None instead iterates `sample`
    directly, so a whole-epoch view can be streamed off disk without holding it in memory.
    """
    lookup = {} if lookup is None else lookup
    g = PseudonymGraph()
    pairs = sample if indices is None else (sample[i] for i in indices)
    for tx, _ in pairs:
        ins = _in_addrs(tx)
        if not ins:
            continue
        srcs = {lookup.get(a, a) for a in ins}
        for axis, fn in AXES.items():
            try:
                value = fn(tx)
            except Exception:                       # a malformed or partial tx, not a bug
                g.skipped[axis] += 1                # counted, never silent: an axis that
                continue                            # dies on every tx must be visible
            g.base_rates[axis][value] += 1
            for s in srcs:
                g._vertex(s)["axes"][axis][value] += 1
        for s in srcs:
            v = g._vertex(s)
            v["txs"] += 1
            v["coins"].update(a for a in ins if lookup.get(a, a) == s)
        for addr, val in _out_addrs(tx):
            if val < min_value:
                continue
            dst = lookup.get(addr, addr)
            g._vertex(dst)["coins"].add(addr)
            for s in srcs:
                if s == dst:
                    g.vertices[s]["self_transfers"] += 1
                    continue
                e = g.edges.setdefault((s, dst), {"transfers": 0, "value": 0})
                e["transfers"] += 1
                e["value"] += val
                g._out[s].add(dst)
                g._in[dst].add(s)
    return g
