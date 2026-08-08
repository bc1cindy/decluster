"""Cost-function contract.

Every quantity here is an attacker's weight-of-evidence / lower bound under no auxiliary
information, never a positive "bits of privacy". Sign discipline: leak and topology may penalise;
the amount channel is REFUSE-ONLY (it can cut a coin from the graph, never add anonymity).
"""
from dataclasses import dataclass

from .cluster import cluster_topology_weight, counterparty_bits
from .ancestry import ancestry_entropy
from .path_count import path_count_anonymity


@dataclass(frozen=True)
class CutCandidate:
    index: int
    value: int
    log_w: float
    exact: bool = False


def leak_bits(tx_a, tx_b, combiner):
    """Fingerprint leak in bits: the combiner's Σ −log₂p weight-of-evidence for tx_a vs tx_b."""
    return combiner.score(tx_a, tx_b)


def amount_cuts(inputs, outputs, oracle, cut_threshold=1.0, count_oracle=None):
    """Amount-channel linkage CANDIDATES — directional, not a proof. The oracle's per-coin `log_w` is
    a knee-truncated lower bound on the coin's ambiguity, so a LOW value only *flags a candidate* (few
    small balancing subsets were found); it does not prove low ambiguity, since a real balance may need
    more coins than the truncation counts. Refuse-only: returns candidate cuts, never a positive term,
    and a dense coinjoin (high log_w everywhere) yields none. Coins with `log_w is None` (unreachable
    within the truncation) are skipped, not cut.

    `count_oracle`, when given, corroborates each cut with the TX-LEVEL exact-count flag
    (`count_oracle(inputs, outputs)["kind"] == "exact"`, matching `counting.w_total`'s shape): when the
    tx's total W(E) is exact, no knee-truncation bites, so the per-coin `log_w` from `oracle` is itself
    untruncated and the cut is RIGOROUS (`exact=True`); when the count is approximate (Sasamoto) or
    off-regime — or `count_oracle` is not given (default `None`) — the per-coin `log_w` stays a lower
    bound and the cut remains a candidate (`exact=False`, today's behavior). dss exposes the exact
    W(E) per TRANSACTION, not per coin, so this is a tx-level corroboration, never a fabricated
    per-coin exact count. `oracle(inputs, outputs)` follows the dss.per_coin_density shape."""
    report = oracle(list(inputs), list(outputs))
    exact = count_oracle is not None and count_oracle(list(inputs), list(outputs)).get("kind") == "exact"
    return [CutCandidate(c["index"], c["value"], c["log_w"], exact=exact)
            for c in report["coins"]
            if c["log_w"] is not None and c["log_w"] <= cut_threshold]


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
    question is HOW the three channels combine into one cost (Liebig-min vs weighted; see
    docs/superpowers/specs/2026-07-27-construction-cost-design.md) — pass `combine=True` to hit that
    deferred raise explicitly. No combination formula is invented here."""
    if combine:
        raise NotImplementedError(
            "construction-cost channel combination is not defined yet: composing leak/topology/"
            "target into one scalar (Liebig vs weighted) is an open design question")
    return {"leak": leak, "topology": topology, "target": target_fn}


def dss_oracle(inputs, outputs):
    """Default production amount oracle: the dense-subset-sum per-coin density/ambiguity signal.
    Lazy import so decluster.cost loads without the compiled `dss` module (build: maturin develop)."""
    import dss
    return dss.per_coin_density(list(inputs), list(outputs))
