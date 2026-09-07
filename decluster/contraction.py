"""Contract a view's clustering into the pseudonym graph the matching algorithm consumes.

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

from .extractors import NA, locktime_policy, x_fee_rate, x_input_order, x_version
from .tx_addrs import in_addrs, out_addrs

# The axes RESULTS-attribute-drift.md finds stable across a one-week gap. The high-drift
# axes (output types, feerate bucket, change position) are deliberately absent: at 4-8x the
# drift they do not survive the boundary they would be compared across.
AXES = {"version": x_version, "input_order": x_input_order,
        "locktime": locktime_policy, "fee_rate": x_fee_rate}


def _fold(store, key, val, height):
    """Add one transfer to the folded record at `key`, extending its value and height span."""
    e = store.get(key)
    if e is None:
        store[key] = {"transfers": 1, "value": val, "first": height, "last": height}
        return
    e["transfers"] += 1
    e["value"] += val
    if height < e["first"]:
        e["first"] = height
    elif height > e["last"]:
        e["last"] = height


class PseudonymGraph:
    """Contracted view. Vertices are clusters; `edges[(src, dst)]` is the single directed
    edge folding every transfer from src to dst, carrying how many there were and how much
    value moved. Value is kept because connectivity means a plausible flow, not merely a
    traceable one, so a matcher may discount an edge that only dust created.

    A transfer whose destination is its own source is a loop, which the user network has and
    which no ordered pair can hold. `self_edges[vid]` folds those under the same schema as an
    edge, so the value and the height span survive contraction there too; the vertex record's
    `self_transfers` is the same count, kept because that record is what gets serialised."""

    def __init__(self, axes=True):
        self.axes = axes                # whether vertex records carry the per-axis counters
        self.vertices = {}
        self.edges = {}
        self.self_edges = {}            # vid -> the folded loop, same attributes as an edge
        self.edge_sig = {}              # (src, dst) -> the axis values of its first transfer
        self.base_rates = {axis: Counter() for axis in AXES}
        self.skipped = Counter()      # axis -> transactions it could not be read from
        self.unattributed = 0         # transactions whose transfers could not be attributed
        self._out = defaultdict(set)
        self._in = defaultdict(set)

    def _vertex(self, vid):
        # Not setdefault: it builds the default on every hit, and this is called once per
        # (transaction, source). The per-axis Counters are the vertex record's bulk — 681 B
        # against 191 B without them — so a structure-only run does not allocate them at all.
        v = self.vertices.get(vid)
        if v is None:
            v = {"coins": 0, "txs": 0, "self_transfers": 0}
            if self.axes:
                v["axes"] = {axis: Counter() for axis in AXES}
            self.vertices[vid] = v
        return v

    def neighbours(self, vid):
        # Read through `.get`: indexing a defaultdict creates an empty set for every vertex
        # merely asked about, and a full degree sweep asks about all of them. The union is
        # written to build the same set the defaultdict form did, in the same order — the
        # matcher breaks score ties on iteration order, so a different one moves results.
        out, inn = self._out.get(vid), self._in.get(vid)
        if out is None and inn is None:
            return set()
        return (out or set()) | (inn or set())

    def degree(self, vid):
        return len(self.neighbours(vid))

    def attribute(self, vid, axis):
        """The vertex's distribution over an axis, as a lift over this view's own base rate.
        1.0 means the vertex looks exactly like its view; the normalisation is what makes
        the value comparable to a vertex measured in another view."""
        record = self.vertices[vid]
        if "axes" not in record:                # structure-only view: nothing was counted
            return {}
        counts = record["axes"][axis]
        total = sum(counts.values())
        base_total = sum(self.base_rates[axis].values())
        if not total or not base_total:
            return {}
        out = {}
        for value, n in counts.items():
            base = self.base_rates[axis].get(value, 0) / base_total
            out[value] = (n / total) / base if base else float("inf")
        return out


def transfer_counts(sample, lookup=None, min_value=0, max_sources=1):
    """How many transfers each cluster takes part in, in one cheap pass. Distinct degree is
    at most this, so thresholding on it never drops a vertex that would have cleared the
    same threshold on degree — which is what makes it safe as a pre-filter. `max_sources`
    must match the value `contract` will be called with, or the pre-filter counts edges the
    contraction never creates."""
    lookup = {} if lookup is None else lookup
    counts = Counter()
    for tx, _ in sample:
        ins = in_addrs(tx)
        if not ins:
            continue
        srcs = {lookup.get(a, a) for a in ins}
        if len(srcs) > max_sources:
            continue                        # unattributable multi-source tx creates no edges
        for addr, val in out_addrs(tx):
            if val < min_value:
                continue
            dst = lookup.get(addr, addr)
            for s in srcs:
                if s != dst:
                    counts[s] += 1
                    counts[dst] += 1
    return counts


def contract_degrees(sample, indices=None, lookup=None, min_value=0, max_sources=1):
    """The degrees of a contracted view, without contracting it.

    The matcher needs each vertex's degree in the *unfiltered* graph: dropping leaves to fit a
    wide view in memory lowers the degree of everything they hung off and silently reweights
    every score. Getting those by building the whole graph and throwing it away costs more than
    the graph that is kept — on a complete 2016 weekly view, 18.3 s and 1104 MB for a number
    that needs only the adjacency. This walks the same edges under the same `max_sources` bound
    and keeps nothing but the neighbour sets, so the degrees are identical by construction.

    Returns `{vertex: degree}`, including the isolated vertices a transaction registers without
    attributing, which is what `contract(...).degree` over `.vertices` reports.
    """
    lookup = {} if lookup is None else lookup
    out, inn = defaultdict(set), defaultdict(set)
    isolated = set()
    pairs = sample if indices is None else (sample[i] for i in indices)
    for tx, _ in pairs:
        ins = in_addrs(tx)
        if not ins:
            continue
        srcs = {lookup.get(a, a) for a in ins}
        isolated |= srcs
        if len(srcs) > max_sources:
            continue
        for addr, val in out_addrs(tx):
            if val < min_value:
                continue
            dst = lookup.get(addr, addr)
            isolated.add(dst)
            for s in srcs:
                if s == dst:
                    continue
                out[s].add(dst)
                inn[dst].add(s)
    degrees = {}
    for v in isolated:
        o, i = out.get(v), inn.get(v)
        if o is None:
            degrees[v] = 0 if i is None else len(i)
        else:
            degrees[v] = len(o) if i is None else len(o | i)
    return degrees


def contract(sample, indices=None, lookup=None, min_value=0, axes=True, keep=None,
             max_sources=1):
    """Contract one view: fuse each cluster's coins into a vertex and fold the transfers
    between clusters into one attributed directed edge per ordered pair, carrying how many
    transfers it folded, how much value moved, and the block-height span they cover.

    An address absent from `lookup` is its own singleton pseudonym, which is the ordinary
    case under a partial clustering rather than an error. `min_value` drops transfers below
    a threshold, so a dust spray does not manufacture a relationship.

    `indices` selects from a materialised sample; passing None instead iterates `sample`
    directly, so a whole-epoch view can be streamed off disk without holding it in memory.
    `axes=False` skips the attribute counters, which dominate the vertex record: a matcher
    run that uses structure alone does not need them and a wide view may not have room.

    A vertex counts its coins rather than listing them; the addresses stay recoverable from
    the clustering lookup.

    `max_sources` bounds how many distinct source pseudonyms a transaction may have before
    its transfers are treated as unattributable and contribute no edges. An edge is supposed
    to be a transfer of bitcoin from one cluster to another; where several pseudonyms fund a
    transaction, which of them paid which output is exactly what is not observable, and
    asserting every source-destination pair invents relationships. In a coinjoin it invents
    the one relationship the construction is defined not to have, since its participants
    need no economic tie at all. Measured on this slice: 211 transactions with six or more
    source pseudonyms were generating 3.4 million of 4.4 million pairs, 77% of the graph.
    Transactions above the bound still register their vertices and their activity.

    `keep` restricts the graph to a vertex set, dropping edges with an endpoint outside it.
    Paired with `transfer_counts` this excludes the leaves — 57% of a contracted 2026 view
    sits at degree below two — which propagation can neither match nor bridge through, so
    the restriction roughly halves the graph. It drops edges and never adds one: the
    `max_sources` bound is evaluated on the transaction's own sources, before the filter.
    """
    lookup = {} if lookup is None else lookup
    g = PseudonymGraph(axes=axes)
    pairs = sample if indices is None else (sample[i] for i in indices)
    for tx, _ in pairs:
        ins = in_addrs(tx)
        if not ins:
            continue
        height = tx.get("height") or 0
        srcs = {lookup.get(a, a) for a in ins}
        # Attributability is a property of the transaction, decided before the view filter
        # touches it. Intersecting first lets a transaction the contraction refused emit an
        # edge as soon as `keep` has removed all but one of its sources — and the survivor is
        # systematically the hub, so the filter invents exactly the relationships the bound
        # exists to withhold.
        attributable = len(srcs) <= max_sources
        if keep is not None:
            srcs &= keep
            if not srcs:
                continue
        sig = None
        if axes:
            sig = []
            for axis, fn in AXES.items():
                try:
                    value = fn(tx)
                except Exception:                   # a malformed or partial tx, not a bug
                    g.skipped[axis] += 1            # counted, never silent: an axis that
                    continue                        # dies on every tx must be visible
                if value == NA:                     # the export does not say. Recording it as a
                    g.skipped[axis] += 1            # value made every vertex in an address-only
                    continue                        # slice agree on the axis for free
                g.base_rates[axis][value] += 1
                sig.append(value)
                for s in srcs:
                    g._vertex(s)["axes"][axis][value] += 1
            sig = tuple(sig)
        for s in srcs:
            v = g._vertex(s)
            v["txs"] += 1
            v["coins"] += sum(1 for a in ins if lookup.get(a, a) == s)
        if not attributable:
            g.unattributed += 1
            continue
        for addr, val in out_addrs(tx):
            if val < min_value:
                continue
            dst = lookup.get(addr, addr)
            if keep is not None and dst not in keep:
                continue
            g._vertex(dst)["coins"] += 1
            for s in srcs:
                if s == dst:
                    g.vertices[s]["self_transfers"] += 1
                    _fold(g.self_edges, s, val, height)
                    continue
                key = (s, dst)
                # Reid and Harrigan label every user-network edge with value *and* time. The
                # span is what separates a relationship that recurs from a one-off, which is
                # the property cross-view matching actually depends on.
                _fold(g.edges, key, val, height)
                if axes and key not in g.edge_sig:
                    # The framework wants the statistical features to inform the EDGE
                    # attributes too, not only the vertices. Stored as the axis values of
                    # the transfer that created the edge rather than a distribution over
                    # all of them: 93% of edges carry a single transfer, so for almost all
                    # of them the two are the same thing, and a Counter per edge is not
                    # affordable at slice scale.
                    g.edge_sig[key] = sig
                g._out[s].add(dst)
                g._in[dst].add(s)
    return g
