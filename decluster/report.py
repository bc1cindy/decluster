"""Fused measurement report — orchestrates the construction/measurement contract on a real tx.
Assembles existing tested terms (NO new science): the per-tx amount cuts and the per-output
ancestry target are ALWAYS computed (they are intrinsic to the tx); the pairwise leak and topology
are computed ONLY when the caller supplies the graph context that makes a pair meaningful, else they
are None (never fabricated). Every number is an attacker lower bound under no auxiliary information,
not a privacy score; the target's headline is min_entropy (the conservative, defender-side read)."""
from .cost import amount_cuts, topology_bits, leak_bits, dss_oracle
from .ancestry import ancestry_entropy, dss_link_oracle

FOOTING = ("attacker lower bounds under no auxiliary information; not a privacy score. target "
           "headline is min_entropy (the conservative, defender-side read); shannon is the "
           "optimistic upper read.")


def _spendable_vouts(tx):
    """Output indices worth a provenance walk: not OP_RETURN and positive value."""
    vouts = []
    for i, o in enumerate(tx["vout"]):
        if o.get("scriptpubkey_type") == "op_return":
            continue
        if o.get("value", 0) <= 0:
            continue
        vouts.append(i)
    return vouts


def report(tx, combiner=None, neigh=None, entities=None, pair=None,
           oracle=None, link_oracle=None, fetch=None, depth=6, targets=None):
    """Fused measurement view of a real transaction `tx` (esplora/mempool.space JSON). See module
    docstring for the always-vs-conditional term policy and the lower-bound footing."""
    if oracle is None:
        oracle = dss_oracle
    if link_oracle is None:
        link_oracle = dss_link_oracle
    if fetch is None:
        from .fetch import fetch_tx
        fetch = fetch_tx
    txid = tx["txid"]
    in_vals = [v["prevout"]["value"] for v in tx["vin"]]
    out_vals = [o["value"] for o in tx["vout"]]
    amount = amount_cuts(in_vals, out_vals, oracle)
    vouts = targets if targets is not None else _spendable_vouts(tx)
    targets_out = {}
    for vout in vouts:
        targets_out[vout] = ancestry_entropy(
            (txid, vout), depth=depth, fetch=fetch, link_oracle=link_oracle)
    leak = None
    if pair is not None:
        if combiner is None:
            from .combiner import Combiner
            combiner = Combiner.from_library()
        leak = leak_bits(tx, pair, combiner)
    topology = None
    if neigh is not None and entities is not None:
        topology = topology_bits(entities[0], entities[1], neigh)
    return {"txid": txid, "amount": amount, "targets": targets_out,
            "leak": leak, "topology": topology, "footing": FOOTING}


def print_report(rep):
    """Human-readable dump of report()'s dict."""
    print(f"== fused report {rep['txid']} ==")
    print(f"  amount: {len(rep['amount'])} refuse-only cut candidate(s)")
    for c in rep["amount"]:
        print(f"    cut idx {c.index} value {c.value} log_w {c.log_w}")
    for vout, t in rep["targets"].items():
        print(f"  target vout {vout}: min_entropy={t['min_entropy']:.3f} bits (lower bound) "
              f"shannon={t['shannon']:.3f} absorbers={t['n_absorbers']} truncated={t['truncated']}")
    print(f"  leak: {rep['leak']}   topology: {rep['topology']}")
    print(f"  [{rep['footing']}]")
