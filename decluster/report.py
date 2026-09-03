"""Fused measurement report — orchestrates the construction/measurement contract on a real tx.
Assembles existing tested terms (NO new science): the per-tx amount cuts and the per-output
ancestry target are ALWAYS computed (they are intrinsic to the tx); the pairwise leak and topology
are computed ONLY when the caller supplies the graph context that makes a pair meaningful, else they
are None (never fabricated). `forced` joins them on the same footing: conservation needs one
participant's input to be known, which the transaction alone does not give. Every number is an
attacker lower bound under no auxiliary information, not a privacy score. By default (`subjective=
True`) the target's headline is fused_min_entropy — the §04 subjective-fused anonymity set;
min_entropy is the graph-only (no-subjective) baseline it can only narrow, never widen. It is NOT read
as a lower bound on the number of graph cuts an adversary needs: the framework offers that reading for
an output's entropy, and PAPER §11 declines it, because whether it transfers to the absorber-model
entropy computed here — which is over a boundary distribution rather than over graph edges — is not
established. The number is reported without it. The fused reading is the CONSERVATIVE minimum of the graph-only and subjective-fused
min-entropy/shannon: subjective evidence can only narrow the anonymity set, never widen it, so a raw
fusion that (via a same-owner boost favoring a graph-minority input) ends up spreading mass instead of
concentrating it is clamped down to the graph-only baseline. This makes fused_min_entropy <= min_entropy
(and fused_shannon <= shannon) an invariant by construction, not just an empirical tendency. Pass
`subjective=False` to opt out to the graph-only baseline alone.

`forced` is reported here, not scored: it is an attribution, and the engine's amount channel may only
refuse (PAPER §1), so it never reaches `cluster_refined`."""
from .cost import amount_cuts, topology_bits, leak_bits, dss_oracle
from .ancestry import ancestry_entropy, value_flow_link_oracle
from .conservation import forced_in_round

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
           oracle=None, link_oracle=None, fetch=None, depth=6, targets=None,
           known_input=None, subjective=True, cluster_of=None, count_oracle=None):
    """Fused measurement view of a real transaction `tx` (esplora/mempool.space JSON). See module
    docstring for the always-vs-conditional term policy and the lower-bound footing. `subjective=True`
    (default) adds the §04 subjective-fused readout (fused_min_entropy/fused_shannon) to each target,
    on top of the graph-only keys; `subjective=False` opts out to the graph-only shape. `cluster_of`
    (a `{address: cluster_id}` from `cluster_refined`) folds the clustering into the §04 subjective
    matrix — the cluster result feeds the anonymity set — alongside the default address-reuse source."""
    if oracle is None:
        oracle = dss_oracle
    if link_oracle is None:
        link_oracle = value_flow_link_oracle
    if fetch is None:
        from .fetch import fetch_tx
        fetch = fetch_tx
    txid = tx["txid"]
    in_vals = [v["prevout"]["value"] for v in tx["vin"]]
    out_vals = [o["value"] for o in tx["vout"]]
    amount = amount_cuts(in_vals, out_vals, oracle, count_oracle=count_oracle)
    vouts = targets if targets is not None else _spendable_vouts(tx)
    targets_out = {}
    for vout in vouts:
        entry = dict(ancestry_entropy((txid, vout), depth=depth, fetch=fetch, link_oracle=link_oracle))
        if subjective:
            from .anonymity_set import (provenance_anonymity_fused, subjective_oracle_for,
                                         anonymity_bits)
            sub_oracle = subjective_oracle_for(cluster_of)
            fdist = provenance_anonymity_fused((txid, vout), sub_oracle, depth=depth, fetch=fetch,
                                                link_oracle=link_oracle)
            fb = anonymity_bits(fdist)
            entry["fused_min_entropy"] = min(fb["min_entropy"], entry["min_entropy"])
            entry["fused_shannon"] = min(fb["shannon"], entry["shannon"])
        targets_out[vout] = entry
    leak = None
    if pair is not None:
        if combiner is None:
            from .combiner import Combiner
            combiner = Combiner.from_library()
        leak = leak_bits(tx, pair, combiner)
    topology = None
    if neigh is not None and entities is not None:
        topology = topology_bits(entities[0], entities[1], neigh)
    forced = None
    if known_input is not None:
        # `[(value, forced, present)]` — outputs no other participant could have
        # funded. Empty is the common answer; it takes a participant large
        # relative to the round for the inequality to bite (PAPER §9).
        forced = forced_in_round(tx, known_input)
    return {"txid": txid, "amount": amount, "targets": targets_out,
            "leak": leak, "topology": topology, "forced": forced,
            "footing": FOOTING}


def print_report(rep):
    """Human-readable dump of report()'s dict."""
    print(f"== fused report {rep['txid']} ==")
    print(f"  amount: {len(rep['amount'])} refuse-only cut candidate(s)")
    for c in rep["amount"]:
        print(f"    cut idx {c.index} value {c.value} log_w {c.log_w}")
    for vout, t in rep["targets"].items():
        base = (f"  target vout {vout}: min_entropy={t['min_entropy']:.3f} bits (graph-only) "
                f"shannon={t['shannon']:.3f} absorbers={t['n_absorbers']} truncated={t['truncated']}")
        if "fused_min_entropy" in t:
            base += f"  | FUSED min_entropy={t['fused_min_entropy']:.3f} bits"
        print(base)
    if rep["forced"] is None:
        print("  forced: n/a (no participant input supplied)")
    elif not rep["forced"]:
        print("  forced: none — the others could have funded every output")
    else:
        for value, n, present in rep["forced"]:
            print(f"  forced: {n} of {present} output(s) at {value} sat are the participant's")
    print(f"  leak: {rep['leak']}   topology: {rep['topology']}")
    print(f"  [{rep['footing']}]")
