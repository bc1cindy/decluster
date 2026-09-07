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
from .extractors import NA, locktime_policy, x_fee_rate, x_input_order, x_uih, x_version
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


def _union_tracking_size(uf, size, addrs):
    """Union a transaction's inputs, keeping a root -> member-count map current.

    The doubt gate asks whether a merge would join two established clusters, and answering that
    by rescanning the union-find once per transaction is quadratic on a real slice.
    """
    # Fewer than two distinct addresses is not a merge, and must not touch the union-find:
    # `find` would register the address as a singleton and put it in the returned lookup, where
    # the reference implementation leaves it absent.
    addrs = list(dict.fromkeys(addrs))
    if len(addrs) < 2:
        return
    roots = {uf.find(a) for a in addrs}
    merged = sum(size.get(r, 1) for r in roots)
    first = addrs[0]
    for a in addrs[1:]:
        uf.union(first, a)
    new_root = uf.find(first)
    for r in roots:
        if r != new_root:
            size.pop(r, None)
    size[new_root] = merged


def merge_objections(tx):
    """What the transaction says against reading its inputs as one owner, counted.

    Zero is the conspicuous case: nothing here argues against common-input ownership, so the merge
    can be made before any doubtful one and its result becomes context for judging those. Each
    objection is decidable from the spending transaction alone and comes from a published tell:

      unnecessary input   some input already covers the largest output, so the others were not
                          needed to fund it and another participant may have contributed one.
      mixed input types   wallets differ in the script types they spend, so inputs that disagree
                          on type have more than one plausible contributor.

    Returns None when the transaction carries neither signal, which is not the same as zero. An
    address-only export cannot be ranked at all, and reading absence of evidence as absence of
    objection would put every transaction in the conspicuous tier for free.
    """
    vin = tx.get("vin", [])
    if len(vin) < 2:
        return 0
    prevouts = [v.get("prevout") or {} for v in vin]
    types = {p.get("scriptpubkey_type") for p in prevouts}
    have_types = None not in types
    have_values = (all(p.get("value") is not None for p in prevouts)
                   and all(o.get("value") is not None for o in tx.get("vout", [])))
    if not have_types and not have_values:
        return None
    objections = 0
    if have_values and x_uih(tx) != "none":
        objections += 1
    if have_types and len(types) > 1:
        objections += 1
    return objections


def merge_order(sample):
    """Sample positions ordered most conspicuous first, ties keeping their original order.

    The framework asks for the clustering to begin with the transactions that argue least against
    themselves and proceed to the next most, so that the doubtful ones are judged against a
    partition built from unambiguous evidence rather than against whatever the block order
    happened to supply. Unrankable transactions sort last, since nothing is known in their favour.

    Raises when the sample carries no rankable evidence at all: staging would then be a no-op
    dressed as a decision, and the caller should know its export cannot support it.
    """
    scored = [(merge_objections(tx), i) for i, (tx, _) in enumerate(sample)]
    # Judge rankability on the transactions the order actually decides about. A single-input
    # transaction has nothing to merge and so scores zero for free; counting those would let an
    # address-only export look rankable and stage into a no-op.
    mergeable = [scored[i][0] for i, (tx, _) in enumerate(sample) if len(tx.get("vin", [])) >= 2]
    if mergeable and all(objections is None for objections in mergeable):
        raise ValueError(
            "no multi-input transaction in this sample carries the input values or script types "
            "that rank a merge's conspicuousness; an address-only export cannot be staged")
    ranked = sorted(range(len(scored)),
                    key=lambda k: (scored[k][0] is None, scored[k][0] or 0, k))
    return ranked


def _merge_pass(sample, order, refuse, doubt_min_side):
    """Apply the merges in `order`, returning the union-find and the positions eligible for a
    change link — the transactions whose inputs already stood in one cluster when they were
    reached, which is a property of the order and so is returned with it rather than read
    back off the finished partition."""
    uf = UF()
    size = {}                       # root -> addresses under it, so the doubt gate stays linear
    eligible = set()
    for tx_index in order:
        tx, _ = sample[tx_index]
        ins = _in_addrs(tx)
        # Do not bootstrap a change link from the CIOH edge currently under examination.
        # Require earlier evidence that all inputs already belong to one cluster; otherwise a
        # collaborative transaction could be mistaken for a unilateral spend.
        if ins and all(a in uf.p for a in ins) and len({uf.find(a) for a in ins}) == 1:
            eligible.add(tx_index)
        if not refuse:
            _union_tracking_size(uf, size, ins)
            continue
        if is_coinjoin(tx):
            continue
        if len(ins) < 2:
            continue
        parts = _demix_participants(tx)
        if parts is None:
            if doubt_min_side and (merge_objections(tx) or 0) > 0:
                roots = {uf.find(a) for a in ins}
                if sum(1 for r in roots if size.get(r, 1) >= doubt_min_side) >= 2:
                    continue          # would fuse two established clusters on doubted evidence
            _union_tracking_size(uf, size, ins)
            continue
        for group in parts.values():
            first = group[0]
            for a in group[1:]:
                uf.union(first, a)
    return uf, eligible


def cluster_addresses(sample, refuse=True, change_link=False, staged=False,
                      doubt_min_side=0):
    """{address: cluster id} over the WHOLE sample. The lookup is global on purpose: it is
    what lets a cluster keep one identity across the partition.

    `staged` clusters the most conspicuous transactions first (`merge_order`) instead of in block
    order. On its own that changes nothing — union-find over a fixed set of merges is
    order-independent, and the one decision that reads the partition built so far, change
    eligibility, is taken in sample order under either setting — so it is paired with
    `doubt_min_side`, which is what the order is for: a transaction that argues against itself
    (`merge_objections` above zero) is declined when its inputs already span two clusters of that
    size or more, because that merge would fuse two established entities on evidence the
    transaction itself undermines. The conspicuous merges run first precisely so that "already
    established" means built from unambiguous evidence rather than from whatever the block order
    happened to supply. Zero disables the gate. Both need an export carrying input values or
    script types.

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
    if staged and change_link:
        # Eligibility is read off the partition standing before each transaction, so it is a
        # property of the order it is read in. Take it in sample order, the same order the
        # unstaged run takes it in, so that staging changes which merges are judged against
        # which context and nothing else.
        _, change_eligible = _merge_pass(sample, range(len(sample)), refuse, doubt_min_side)
        uf, _ = _merge_pass(sample, merge_order(sample), refuse, doubt_min_side)
    else:
        order = merge_order(sample) if staged else range(len(sample))
        uf, change_eligible = _merge_pass(sample, order, refuse, doubt_min_side)
    if change_link:
        # Optimal-change (the unnecessary-input heuristics, cit-15/16), collapse-safe: only link
        # a *fresh* change address (never seen as an input) so it cannot merge two existing
        # clusters -- it only extends one. Eligibility above is a prefix condition, so this pass
        # is sensitive to the sample's own sequence: a different sequence is a different set of
        # links, and only the staging flag is held not to move it.
        from .change_special import label_optimal_change
        from .change_gt import out_addr
        input_seen = set()
        for tx, _ in sample:
            input_seen.update(_in_addrs(tx))
        for tx_index, (tx, _) in enumerate(sample):
            if tx_index not in change_eligible:
                continue
            # Optimal-change is a unilateral-transaction heuristic. When transaction shape or
            # amount de-mixing indicates multiple participants, input ordering cannot identify
            # which participant owns the output, so abstain.
            if is_coinjoin(tx) or _demix_participants(tx) is not None:
                continue
            ci = label_optimal_change(tx)          # unique change index or None (abstains otherwise)
            if ci is None:
                continue
            change = out_addr(tx, ci)
            ins = _in_addrs(tx)
            if change and change not in input_seen and ins:
                uf.union(ins[0], change)
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


class _ViewLookup:
    """One view's read of a split clustering: a straddling cluster answers under this view's
    own pseudonym, every other cluster under its own id.

    The tag is applied on lookup rather than materialised. Two per-view dicts would be twice
    the largest structure in a multi-epoch run, and the base map is needed either way.
    """
    __slots__ = ("_base", "_split", "_suffix")

    def __init__(self, base, split_cids, suffix):
        self._base, self._split, self._suffix = base, split_cids, suffix

    def get(self, address, default=None):
        cid = self._base.get(address)
        if cid is None:
            return default
        # The compact backend keys clusters by dense integer, the dict one by address.
        return f"{cid}{self._suffix}" if cid in self._split else cid


def view_lookup(lookup, split_cids, suffix):
    """The lookup to contract one view with. `suffix` is "#a" or "#b"."""
    return _ViewLookup(lookup, split_cids, suffix)


def split_clusters_by_view(lookup, view_a_addrs, frac, rng):
    """Choose the clusters that straddle the view boundary, so each view can contract them
    under its own pseudonym. Returns `(split_cids, {pseudonym: original cluster})`.

    `split_clusters` fragments by drawing addresses at random, which leaves both halves
    present in both views, so the matcher can satisfy itself with the identity match and
    never has to attempt the rejoin. Splitting along the boundary removes that escape: one
    pseudonym lives on each side, and the only correspondence available is the discovery.
    It is also the natural form of the premise, a clustering that has failed to link a
    user's activity across time.

    Which side an address falls on cannot decide its tag globally. An address used in *both*
    windows is in `view_a_addrs`, so tagging by that alone marks it `#a` everywhere and view
    B ends up holding `C#a` as well as `C#b` — the identity match, structurally the better
    one, graded wrong. Each view is therefore contracted under its own `view_lookup`, which
    is also the framework's construction: each epoch is clustered separately.
    """
    # Record only which side(s) each cluster touches. The previous implementation also built
    # cid -> [all member addresses], duplicating the largest structure in a multi-epoch run.
    sides = {}
    for addr, cid in lookup.items():
        sides[cid] = sides.get(cid, 0) | (1 if addr in view_a_addrs else 2)
    split_cids = {cid for cid, side in sides.items() if side == 3 and rng.random() < frac}
    origin = {}
    for cid in set(lookup.values()):
        if cid in split_cids:
            origin[f"{cid}#a"] = cid
            origin[f"{cid}#b"] = cid
        else:
            origin[cid] = cid
    return split_cids, origin


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


def partition_coins(sample, scheme="epoch", bounds=None, core_frac=0.01, n_views=2,
                    min_side=2):
    """Split the sample into views, returning one list of sample indices per view.

    epoch             by block height, the trivial partition the framework names as its
                      example. `bounds` is [(lo, hi), ...]; without it the height range is
                      halved.
    coinjoin_boundary a coinjoin is where co-spending stops implying common ownership, so
                      it is a natural seam: transactions before and after form the views and
                      the coinjoins themselves are the boundary, in no view.
    ambiguity_cut     the framework's preferred scheme, the "opposite" of expander
                      decomposition. See `ambiguity_partition`; note it needs two passes,
                      so `sample` must be a list rather than an iterator here. `n_views`
                      keeps the largest N components, the framework's n > 2 generalization.
    collapse          cut along the cluster-collapse events themselves — the merges that would
                      fuse two already-substantial clusters — then split the survivors by height
                      into `n_views` bands. See `collapse_partition`.

    A cut removes the boundary from the views and keeps the rest; it does not discard the
    vertices incident to it.
    """
    if scheme == "epoch":
        heights = [tx.get("height") or 0 for tx, _ in sample]
        if bounds is None:
            bounds = height_bands(heights, n_views)
        return [[i for i, h in enumerate(heights) if lo <= h <= hi] for lo, hi in bounds]

    if scheme == "coinjoin_boundary":
        seam = [i for i, (tx, _) in enumerate(sample) if is_coinjoin(tx)]
        cut = seam[len(seam) // 2] if seam else len(sample) // 2
        boundary = set(seam)
        return [[i for i in range(cut) if i not in boundary],
                [i for i in range(cut + 1, len(sample)) if i not in boundary]]

    if scheme == "ambiguity_cut":
        return ambiguity_partition(sample, sample, core_frac=core_frac, n_views=n_views)

    if scheme == "decore":
        return decore_partition(sample, core_frac=core_frac, bounds=bounds, n_views=n_views)

    if scheme == "collapse":
        return collapse_partition(sample, min_side=min_side, bounds=bounds, n_views=n_views)

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


def collapse_boundary(sample, min_side=2):
    """The transactions whose common-input merge would fuse two already-substantial clusters.

    Returns `(boundary_indices, uf)` — the sample positions of those transactions, and the
    union-find that results from declining them.

    This is the cut the framework asks for in place of the trivial temporal one: not the busiest
    addresses (`decore_partition`, which cuts by degree and so removes hubs whether or not they
    fuse anything) but the *cluster-collapse* events themselves. A merge that attaches a fresh
    address to one existing cluster only grows it; a merge that joins two clusters of `min_side`
    or more is the one that destroys the distinction between two entities, and it is exactly what
    a competent adversary refuses and what the partition should therefore cut along.

    Detection and refusal are the same pass, which makes the result self-consistent: the clusters
    that survive are the ones the declined merges never joined, so the boundary really is a
    boundary of the clustering it produces. Order is the sample's own, i.e. block order — a
    streaming union-find's view of which cluster was already substantial is causal, and reordering
    the input can move a marginal case either way.
    """
    uf = UF()
    size = {}                       # root -> addresses under it, maintained alongside the union-find
    boundary = []

    def root_of(a):
        r = uf.find(a)
        size.setdefault(r, 1)
        return r

    for i, (tx, _) in enumerate(sample):
        ins = _in_addrs(tx)
        if len(ins) < 2:
            for a in ins:
                root_of(a)
            continue
        roots = {root_of(a) for a in ins}
        if len(roots) >= 2 and sum(1 for r in roots if size[r] >= min_side) >= 2:
            boundary.append(i)
            continue
        merged = sum(size[r] for r in roots)
        first = ins[0]
        for a in ins[1:]:
            uf.union(first, a)
        new_root = uf.find(first)
        for r in roots:
            if r != new_root:
                size.pop(r, None)
        size[new_root] = merged
    return boundary, uf


def height_bands(heights, n_views):
    """`n_views` contiguous height bands covering the range, the last one taking the remainder.

    The framework asks for the n > 2 generalisation of every cut, so the temporal axis every
    scheme falls back on bands the same way. Two schemes used to halve the range whatever
    `n_views` said, which returned two views for a caller that asked for four and reported
    nothing.
    """
    if n_views < 1:
        raise ValueError(f"n_views must be at least 1, not {n_views}")
    lo_h, hi_h = min(heights), max(heights)
    step = max(1, (hi_h - lo_h + 1) // n_views)
    bounds, bottom = [], lo_h
    for index in range(n_views):
        top = hi_h if index == n_views - 1 else min(bottom + step - 1, hi_h)
        bounds.append((bottom, top))
        bottom = top + 1
    return bounds


def collapse_partition(sample, min_side=2, scheme="epoch", bounds=None, n_views=2):
    """Views cut along cluster-collapse regions rather than along time.

    The collapse transactions leave every view (they are the boundary, in none of them) and the
    survivors are split on an axis orthogonal to connectivity — block height by default, into
    `n_views` bands. The orthogonal split is not optional: taking the connected components the cut
    leaves would give vertex-disjoint views that share no entity, and a matcher with nothing to
    rejoin. Cut for ambiguity, split for overlap.
    """
    if scheme != "epoch":
        raise ValueError(f"unknown inner scheme for collapse: {scheme}")
    boundary = set(collapse_boundary(sample, min_side=min_side)[0])
    kept = [i for i in range(len(sample)) if i not in boundary and _in_addrs(sample[i][0])]
    if not kept:
        return [[] for _ in range(n_views)]
    h = {i: (sample[i][0].get("height") or 0) for i in kept}
    if bounds is None:
        lo_h, hi_h = min(h.values()), max(h.values())
        step = max(1, (hi_h - lo_h + 1) // max(1, n_views))
        bounds = []
        b = lo_h
        for k in range(n_views):
            top = hi_h if k == n_views - 1 else min(b + step - 1, hi_h)
            bounds.append((b, top))
            b = top + 1
    return [[i for i in kept if lo <= h[i] <= hi] for lo, hi in bounds]


def decore_partition(sample, core_frac=0.01, scheme="epoch", bounds=None, n_views=2):
    """The ambiguity-cut reformulated so the views actually overlap.

    `ambiguity_partition` removes the dense core and returns its *connected components*,
    which are vertex-disjoint by construction: a cluster (defined by co-spend, i.e. address
    sharing) stays inside one component, so two components share almost no entity and the
    cross-view matcher has nothing to rejoin. This keeps the "de-core" idea — drop the busiest
    `core_frac` of addresses as ambiguous noise from *both* views — but takes the view
    boundary from an axis orthogonal to connectivity (block height by default). An entity
    active on both sides of that axis then appears in both views, restoring the shared-vertex
    overlap the matcher needs. Pair with `split_clusters_by_view` so a straddling entity
    carries a distinct pseudonym per view rather than the trivial identity.
    """
    seen = Counter()
    addrs = []
    for tx, _ in sample:
        a = set(_in_addrs(tx)) | {x for x, _ in _out_addrs(tx)}
        addrs.append(a)
        for x in a:
            seen[x] += 1
    if not seen:
        return [[], []]
    cut = max(1, int(len(seen) * core_frac))
    core = {a for a, _ in seen.most_common(cut)}
    kept = [i for i, a in enumerate(addrs) if a and not (a & core)]
    if scheme == "epoch":
        h = {i: (sample[i][0].get("height") or 0) for i in kept}
        if not h:
            return [[], []]
        if bounds is None:
            bounds = height_bands(list(h.values()), n_views)
        return [[i for i in kept if lo <= h[i] <= hi] for lo, hi in bounds]
    raise ValueError(f"unknown inner scheme for decore: {scheme}")


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
        ins = _in_addrs(tx)
        if not ins:
            continue
        srcs = {lookup.get(a, a) for a in ins}
        if len(srcs) > max_sources:
            continue                        # unattributable multi-source tx creates no edges
        for addr, val in _out_addrs(tx):
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
        ins = _in_addrs(tx)
        if not ins:
            continue
        srcs = {lookup.get(a, a) for a in ins}
        isolated |= srcs
        if len(srcs) > max_sources:
            continue
        for addr, val in _out_addrs(tx):
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
        ins = _in_addrs(tx)
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
