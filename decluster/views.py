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

from .coinjoin_demix import coinjoin_demix
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


def cluster_addresses(sample, refuse=True):
    """{address: cluster id} over the WHOLE sample. The lookup is global on purpose: it is
    what lets a cluster keep one identity across the partition.

    `refuse` declines to apply common-input ownership where the transaction itself argues
    against it, which is the difference between the framework's competent adversary and the
    one whose blind merging collapses clusters. Two rules, both decidable from the spending
    transaction alone:

      coinjoin shape    many inputs against many outputs is where co-spending stops implying
                        common ownership, so no input is merged with any other.
      de-mix partition  when `coinjoin_demix` resolves inputs to distinct participants, only
                        inputs of the same participant merge. Inputs it could not resolve
                        merge with nobody: under refusal, an unresolved input is unknown
                        ownership, not shared ownership.

    Two channels the engine has are absent here and their absence is a real limitation, not
    a simplification: the fingerprint channel compares the *funding* transactions, which for
    a two-day slice lie almost entirely outside it, and the roundness channel is gated on
    the fingerprint disagreeing, so using it alone would refuse ordinary round payments.
    """
    uf = UF()
    for tx, _ in sample:
        if not refuse:
            union_input_addrs(tx, uf)
            continue
        if is_coinjoin(tx):
            continue
        ins = _in_addrs(tx)
        if len(ins) < 2:
            continue
        parts = _demix_participants(tx)
        if parts is None:
            union_input_addrs(tx, uf)
            continue
        for group in parts.values():
            first = group[0]
            for a in group[1:]:
                uf.union(first, a)
    return {a: uf.find(a) for g in uf.groups() for a in g}


def split_clusters(lookup, frac, rng, min_size=2):
    """Fragment a fraction of the clusters into two pseudonyms each, returning
    (split lookup, {pseudonym: original cluster}).

    The framework's premise is that the clustering is *incomplete*, so one user holds
    several pseudonyms and keeps their pseudonymity until the adversary can join them. A
    matcher run against a clustering contracted from itself can only ever recover the
    identity map, which is not new information and cannot feed anything back. Splitting
    deliberately creates the object the matching exists to find: two pseudonyms that are one
    user, with the answer known.
    """
    members = {}
    for addr, cid in lookup.items():
        members.setdefault(cid, []).append(addr)
    out, origin = {}, {}
    for cid, addrs in members.items():
        if len(addrs) < min_size or rng.random() >= frac:
            out.update({a: cid for a in addrs})
            origin[cid] = cid
            continue
        addrs = sorted(addrs)
        rng.shuffle(addrs)
        half = len(addrs) // 2
        for tag, part in ((f"{cid}#0", addrs[:half]), (f"{cid}#1", addrs[half:])):
            origin[tag] = cid
            out.update({a: tag for a in part})
    return out, origin


def split_clusters_by_view(lookup, view_a_addrs, frac, rng):
    """Fragment clusters along the view boundary: the addresses a cluster uses in view A
    become one pseudonym, the rest another.

    `split_clusters` fragments by drawing addresses at random, which leaves both halves
    present in both views, so the matcher can satisfy itself with the identity match and
    never has to attempt the rejoin. Splitting along the boundary removes that escape: one
    pseudonym lives on each side, and the only correspondence available is the discovery.
    It is also the natural form of the premise, a clustering that has failed to link a
    user's activity across time.
    """
    members = {}
    for addr, cid in lookup.items():
        members.setdefault(cid, []).append(addr)
    out, origin = {}, {}
    for cid, addrs in members.items():
        left = [a for a in addrs if a in view_a_addrs]
        right = [a for a in addrs if a not in view_a_addrs]
        if not left or not right or rng.random() >= frac:
            out.update({a: cid for a in addrs})
            origin[cid] = cid
            continue
        for tag, part in ((f"{cid}#a", left), (f"{cid}#b", right)):
            origin[tag] = cid
            out.update({a: tag for a in part})
    return out, origin


def _demix_participants(tx):
    """{participant: [input addresses]} when the de-mix resolves the transaction into two or
    more participants, else None. Returning the partition rather than per-pair verdicts is
    what keeps this linear: a wide consolidation has quadratically many pairs but only as
    many groups as participants."""
    vin = tx.get("vin", [])
    values = [(v.get("prevout") or {}).get("value") for v in vin]
    outs = [o.get("value") for o in tx.get("vout", [])]
    if any(v is None for v in values) or any(o is None for o in outs):
        return None
    assign = coinjoin_demix(values, outs)
    if len(set(assign.values())) < 2:
        return None
    groups = {}
    for i, participant in assign.items():
        addr = (vin[i].get("prevout") or {}).get("scriptpubkey_address")
        if addr:
            groups.setdefault(participant, []).append(addr)
    return {k: v for k, v in groups.items() if v} or None


def partition_coins(sample, scheme="epoch", bounds=None, core_frac=0.01):
    """Split the sample into views, returning one list of sample indices per view.

    epoch             by block height, the trivial partition the framework names as its
                      example. `bounds` is [(lo, hi), ...]; without it the height range is
                      halved.
    coinjoin_boundary a coinjoin is where co-spending stops implying common ownership, so
                      it is a natural seam: transactions before and after form the views and
                      the coinjoins themselves are the boundary, in no view.
    ambiguity_cut     the framework's preferred scheme, the "opposite" of expander
                      decomposition. See `ambiguity_partition`; note it needs two passes,
                      so `sample` must be a list rather than an iterator here.

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
        return ambiguity_partition(sample, sample, core_frac=core_frac)

    raise ValueError(f"unknown scheme: {scheme}")


def ambiguity_partition(pass_one, pass_two, core_frac=0.01, n_views=2):
    """The framework's preferred partition, "the opposite of expander decomposition".

    Expander decomposition finds a *sparse* cut and leaves well-connected components. The
    opposite cuts through the dense core and leaves components that are relatively sparser,
    which is the regime the matching needs: in a dense region every vertex looks like its
    neighbours and identity is ambiguous, while a sparse neighbourhood is distinctive.

    The core is the busiest `core_frac` of addresses. Transactions touching it are the cut
    and join no view; what remains decomposes into connected components, and the largest
    `n_views` become the views. A cluster whose activity only reached across through the
    core now appears in two components under separate pseudonyms, which is exactly the
    correspondence the matcher exists to recover.

    Takes two independent iterators over the same transactions so a slice can be partitioned
    without being held in memory.
    """
    seen = Counter()
    for tx, _ in pass_one:
        for a in set(_in_addrs(tx)) | {a for a, _ in _out_addrs(tx)}:
            seen[a] += 1
    if not seen:
        return [[] for _ in range(n_views)]
    cut = max(1, int(len(seen) * core_frac))
    core = {a for a, _ in seen.most_common(cut)}

    uf = UF()
    members = {}
    for i, (tx, _) in enumerate(pass_two):
        addrs = set(_in_addrs(tx)) | {a for a, _ in _out_addrs(tx)}
        if not addrs or addrs & core:
            continue                                     # the cut itself joins no view
        addrs = sorted(addrs)
        for a in addrs[1:]:
            uf.union(addrs[0], a)
        members[i] = addrs[0]
    comps = {}
    for i, anchor in members.items():
        comps.setdefault(uf.find(anchor), []).append(i)
    return sorted(comps.values(), key=len, reverse=True)[:n_views]


class PseudonymGraph:
    """Contracted view. Vertices are clusters; `edges[(src, dst)]` is the single directed
    edge folding every transfer from src to dst, carrying how many there were and how much
    value moved. Value is kept because connectivity means a plausible flow, not merely a
    traceable one, so a matcher may discount an edge that only dust created."""

    def __init__(self):
        self.vertices = {}
        self.edges = {}
        self.edge_sig = {}              # (src, dst) -> the axis values of its first transfer
        self.base_rates = {axis: Counter() for axis in AXES}
        self.skipped = Counter()      # axis -> transactions it could not be read from
        self.unattributed = 0         # transactions whose transfers could not be attributed
        self._out = defaultdict(set)
        self._in = defaultdict(set)

    def _vertex(self, vid):
        return self.vertices.setdefault(
            vid, {"coins": 0, "txs": 0, "self_transfers": 0,
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


def transfer_counts(sample, lookup=None, min_value=0, max_sources=1):
    """How many transfers each cluster takes part in, in one cheap pass. Distinct degree is
    at most this, so thresholding on it never drops a vertex that would have cleared the
    same threshold on degree — which is what makes it safe as a pre-filter. `max_sources`
    must match the value `contract` will be called with, or the pre-filter counts edges the
    contraction never creates."""
    lookup = {} if lookup is None else lookup
    counts = Counter()
    for tx, _ in sample:
        ins = _in_addrs(tx)
        if not ins:
            continue
        srcs = {lookup.get(a, a) for a in ins}
        if len(srcs) > max_sources:
            g.unattributed += 1
            continue
        for addr, val in _out_addrs(tx):
            if val < min_value:
                continue
            dst = lookup.get(addr, addr)
            for s in srcs:
                if s != dst:
                    counts[s] += 1
                    counts[dst] += 1
    return counts


def contract(sample, indices=None, lookup=None, min_value=0, axes=True, keep=None,
             max_sources=1):
    """Contract one view: fuse each cluster's coins into a vertex and fold the transfers
    between clusters into one attributed directed edge per ordered pair.

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
    the restriction leaves the matching unchanged while roughly halving the graph.
    """
    lookup = {} if lookup is None else lookup
    g = PseudonymGraph()
    pairs = sample if indices is None else (sample[i] for i in indices)
    for tx, _ in pairs:
        ins = _in_addrs(tx)
        if not ins:
            continue
        srcs = {lookup.get(a, a) for a in ins}
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
                g.base_rates[axis][value] += 1
                sig.append(value)
                for s in srcs:
                    g._vertex(s)["axes"][axis][value] += 1
            sig = tuple(sig)
        for s in srcs:
            v = g._vertex(s)
            v["txs"] += 1
            v["coins"] += sum(1 for a in ins if lookup.get(a, a) == s)
        if len(srcs) > max_sources:
            g.unattributed += 1
            continue
        for addr, val in _out_addrs(tx):
            if val < min_value:
                continue
            dst = lookup.get(addr, addr)
            if keep is not None and dst not in keep:
                continue
            g._vertex(dst)["coins"] += 1
            for s in srcs:
                if s == dst:
                    g.vertices[s]["self_transfers"] += 1
                    continue
                key = (s, dst)
                e = g.edges.setdefault(key, {"transfers": 0, "value": 0})
                e["transfers"] += 1
                e["value"] += val
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
