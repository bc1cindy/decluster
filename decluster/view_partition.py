"""Where to cut the coin graph so the sides can be matched against each other.

Cutting by time is the framework's own trivial example. The schemes after it cut along structure
instead: `ambiguity_cut` is the opposite of expander decomposition, keeping the well-connected cores
and spending the ambiguous boundary on the cut, and `collapse` cuts at the merges that would fuse two
already-substantial clusters. Every scheme takes `n_views`, so none of them is limited to two sides.
"""
from collections import Counter

from .monitor import is_coinjoin
from .tx_addrs import in_addrs, out_addrs
from .unionfind import UF


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
        for a in set(in_addrs(tx)) | {a for a, _ in out_addrs(tx)}:
            seen[a] += 1
    if not seen:
        return [[] for _ in range(n_views)]
    cut = max(1, int(len(seen) * core_frac))
    core = {a for a, _ in seen.most_common(cut)}

    uf = UF()
    members = {}
    for i, (tx, _) in enumerate(pass_two):
        addrs = set(in_addrs(tx)) | {a for a, _ in out_addrs(tx)}
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
        ins = in_addrs(tx)
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
    kept = [i for i in range(len(sample)) if i not in boundary and in_addrs(sample[i][0])]
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
        a = set(in_addrs(tx)) | {x for x, _ in out_addrs(tx)}
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
