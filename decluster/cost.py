"""Cost-function contract.

Every quantity here is an attacker's weight-of-evidence / lower bound under no auxiliary
information, never a positive "bits of privacy". Sign discipline: leak and topology may penalise;
the amount channel is REFUSE-ONLY (it can cut a coin from the graph, never add anonymity).
"""
from dataclasses import dataclass

from .cluster import cluster_topology_weight, counterparty_bits
from .ancestry import ancestry_entropy
from .weighted_path_count import path_count_anonymity


@dataclass(frozen=True)
class CutCandidate:
    index: int
    value: int
    log_w: float
    exact: bool = False


def leak_bits(tx_a, tx_b, combiner):
    """Fingerprint leak in bits: the combiner's Σ −log₂p weight-of-evidence for tx_a vs tx_b."""
    return combiner.score(tx_a, tx_b)


def _reachable(log_w):
    """Whether the oracle actually measured this coin, as opposed to failing to reach it.

    Unreachable is spelled as None by some callers and as negative infinity by the dss per-coin
    path; NaN would be a third spelling. All three mean the same thing and none of them is a low
    ambiguity."""
    return log_w is not None and log_w == log_w and log_w != float("-inf")


def amount_cuts(inputs, outputs, oracle, cut_threshold=1.0, count_oracle=None):
    """Amount-channel linkage CANDIDATES — directional, not a proof. The oracle's per-coin `log_w` is
    a knee-truncated lower bound on the coin's ambiguity, so a LOW value only *flags a candidate* (few
    small balancing subsets were found); it does not prove low ambiguity, since a real balance may need
    more coins than the truncation counts. Refuse-only: returns candidate cuts, never a positive term,
    and a dense coinjoin (high log_w everywhere) yields none.

    A coin the truncated search could not reach at all is SKIPPED, not cut — "no balancing subset was
    found" is the absence of a measurement, not a measurement of zero ambiguity. The oracle spells
    that state as negative infinity rather than None, and on a real slice it is the common case:
    98.2% of input coins over 1,428 multi-input transactions, and every input coin in 97% of them.
    Reading it as a low value would cut nearly every coin in the graph.

    The per-coin reading is the last of three steps and is gated on the one before it: classify the
    amounts, evaluate the transaction as a whole, and only then apportion across its coins. A
    transaction whose ambiguity did not resolve at the second step has nothing to apportion, and the
    per-coin oracle answering anyway is the oracle guessing rather than measuring.

    `count_oracle` performs that second step, defaulting to the routed count. It also corroborates
    each cut with the TX-LEVEL exact-count flag
    (`kind == "exact"` with a positive count): when the
    tx's total W(E) is exact, no knee-truncation bites, so the per-coin `log_w` from `oracle` is itself
    untruncated and the cut is RIGOROUS (`exact=True`); when the count is approximate (Sasamoto) or
    off-regime — the per-coin `log_w` stays a lower bound and the cut
    remains a candidate (`exact=False`). dss exposes the exact
    W(E) per TRANSACTION, not per coin, so this is a tx-level corroboration, never a fabricated
    per-coin exact count. `oracle(inputs, outputs)` follows the dss.per_coin_density shape."""
    from .counting import count_w, guaranteed_log_w
    if count_oracle is None:
        count_oracle = count_w
    # Step two before step three. Apportioning ambiguity across the coins of a transaction whose
    # ambiguity as a whole did not resolve is apportioning nothing: measured, a third of the
    # transactions the per-coin oracle spoke for had no transaction-level reading behind them.
    whole = count_oracle(list(inputs), list(outputs))
    if guaranteed_log_w(whole) is None:
        return []
    # An exact count of ZERO is the counter completing and finding no balancing subset, which is
    # what a fee-paying transaction produces under a fee-blind count — the weakest corroboration
    # there is, not the strongest. Rigour requires the count to have found something.
    exact = whole.get("kind") == "exact" and (whole.get("count") or 0) > 0
    report = oracle(list(inputs), list(outputs))
    return [CutCandidate(c["index"], c["value"], c["log_w"], exact=exact)
            for c in report["coins"]
            if _reachable(c["log_w"]) and c["log_w"] <= cut_threshold]


def topology_bits(members_a, members_b, neigh, tau=1.0):
    """Cluster-level N–S counterparty-overlap weight (bits): a shared rare counterparty corroborates
    same owner (+), disjoint neighbourhoods refuse (−). Rarity-weighted, global (field-independent)."""
    cbits = counterparty_bits(neigh)
    return cluster_topology_weight(members_a, members_b, neigh, cbits=cbits, tau=tau)


# The fused measurement view (leak + amount cuts + topology + ancestry target) lives in one place:
# `decluster.report.report` (the per-tx orchestrator). This module holds the leaf terms it composes.


def construction_cost(leak, topology, target_fn=path_count_anonymity, graph=None, combine=False):
    """(A) construction objective — the component terms, structured. `target_fn` is the §07
    path-counting target (`path_count.path_count_anonymity`, now wired) or any compatible target
    (e.g. `ancestry_entropy`); the missing-target blocker is gone, so this no longer raises by
    default. It returns the terms UNCOMBINED: `{"leak": leak, "topology": topology,
    "target": target_fn}` — leak/topology as given, `target_fn` itself as the target marker (this
    function does not invoke it; composing a scalar isn't its job). The only remaining open design
    question is HOW the three channels combine into one cost (Liebig-min vs weighted) — pass
    `combine=True` to hit that deferred raise explicitly. No combination formula is invented
    here."""
    if combine:
        raise NotImplementedError(
            "construction-cost channel combination is not defined yet: composing leak/topology/"
            "target into one scalar (Liebig vs weighted) is an open design question")
    return {"leak": leak, "topology": topology, "target": target_fn}


def boltzmann_oracle(inputs, outputs):
    """Per-coin ambiguity read off the link matrix, in the shape `amount_cuts` consumes.

    `log_w` here is the log-count of outputs an input could plausibly have funded under dss's
    mapping family, which puts it on the same footing as the per-coin density oracle it stands
    beside: a low value means few readings survive *in that family*. Zero does NOT mean the amounts
    settle the assignment — dss's family is a strict restriction of the exact one, and reading a
    one-entry row as certain was measured to assert 1,197 unsettled certainties across 395 of 507
    transactions (`results/RESULTS-exact-oracle-audit.md`). Unlike the density oracle it answers
    when the transaction pays a fee, which is nearly always.
    """
    import math

    from .counting import link_ambiguity

    ambiguity = link_ambiguity(inputs, outputs)
    values = list(inputs)
    return {"coins": [{"role": "in", "index": i, "value": values[i],
                       "log_w": math.log2(n) if n > 0 else None}
                      for i, n in sorted(ambiguity.items()) if i < len(values)]}


def dss_oracle(inputs, outputs):
    """Default production amount oracle: the dense-subset-sum per-coin density/ambiguity signal.
    Lazy import so decluster.cost loads without the compiled `dss` module (build: maturin develop)."""
    import dss
    return dss.per_coin_density(list(inputs), list(outputs))
