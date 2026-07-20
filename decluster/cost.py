"""Cost-function contract.

Every quantity here is an attacker's weight-of-evidence / lower bound under no auxiliary
information, never a positive "bits of privacy". Sign discipline: leak and topology may penalise;
the amount channel is REFUSE-ONLY (it can cut a coin from the graph, never add anonymity).
"""
from dataclasses import dataclass

from .cluster import cluster_topology_weight, counterparty_bits
from .ancestry import ancestry_entropy


@dataclass(frozen=True)
class CutCandidate:
    index: int
    value: int
    log_w: float


def leak_bits(tx_a, tx_b, combiner):
    """Fingerprint leak in bits: the combiner's Σ −log₂p weight-of-evidence for tx_a vs tx_b."""
    return combiner.score(tx_a, tx_b)


def amount_cuts(inputs, outputs, oracle, cut_threshold=1.0):
    """Amount-channel linkage CANDIDATES — directional, not a proof. The oracle's per-coin `log_w` is
    a knee-truncated lower bound on the coin's ambiguity, so a LOW value only *flags a candidate* (few
    small balancing subsets were found); it does not prove low ambiguity, since a real balance may need
    more coins than the truncation counts. Refuse-only: returns candidate cuts, never a positive term,
    and a dense coinjoin (high log_w everywhere) yields none. Coins with `log_w is None` (unreachable
    within the truncation) are skipped, not cut. A rigorous cut needs an exact count and is deferred.
    `oracle(inputs, outputs)` follows the dss.per_coin_density shape."""
    report = oracle(list(inputs), list(outputs))
    return [CutCandidate(c["index"], c["value"], c["log_w"])
            for c in report["coins"]
            if c["log_w"] is not None and c["log_w"] <= cut_threshold]


def topology_bits(members_a, members_b, neigh, tau=1.0):
    """Cluster-level N–S counterparty-overlap weight (bits): a shared rare counterparty corroborates
    same owner (+), disjoint neighbourhoods refuse (−). Rarity-weighted, global (field-independent)."""
    cbits = counterparty_bits(neigh)
    return cluster_topology_weight(members_a, members_b, neigh, cbits=cbits, tau=tau)


# The fused measurement view (leak + amount cuts + topology + ancestry target) lives in one place:
# `decluster.report.report` (the per-tx orchestrator). This module holds the leaf terms it composes.


def construction_cost(leak, topology, target_fn=ancestry_entropy, graph=None):
    """(A) construction objective — composition DEFERRED. Combining the terms into one cost is an
    open design question: it depends on the path-counting `target` (still a stub) and on how the
    channels combine (Liebig vs weighted), which is not settled until that engine and the metric
    design land. The signature is reserved so callers can be written against it, but it raises until
    the composition is defined — so no caller relies on a provisional, possibly wrong-signed formula."""
    raise NotImplementedError(
        "construction-cost composition is not defined yet: it depends on the path-counting "
        "target and the channel-combination design")


def dss_oracle(inputs, outputs):
    """Default production amount oracle: the dense-subset-sum per-coin density/ambiguity signal.
    Lazy import so decluster.cost loads without the compiled `dss` module (build: maturin develop)."""
    import dss
    return dss.per_coin_density(list(inputs), list(outputs))
