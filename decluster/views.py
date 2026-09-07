"""Cluster addresses into wallets, then split each cluster into one pseudonym per view.

The clustering is the adversary's partial knowledge: co-spending joins addresses, and
`merge_objections` lets a channel refuse a join the co-spend would otherwise force.
`split_clusters_by_view` then models the incomplete-clustering premise the matching algorithm
assumes — a cluster straddling a view boundary becomes a separate pseudonym on each side, and
rejoining them is what the matcher is asked to do.
"""
from .coinjoin_demix import coinjoin_demix
from .extractors import x_uih
from .monitor import is_coinjoin
from .tx_addrs import in_addrs
from .unionfind import UF


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
        ins = in_addrs(tx)
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
            input_seen.update(in_addrs(tx))
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
            ins = in_addrs(tx)
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
