"""§04-fusion validation at scale, via LIVE ancestry fetch (mempool.space) — not the shallow
cache-only walk. Oversamples multi-input targets, keeps the ones whose graph-only walk actually
BRANCHES (>=2 absorbers, not truncated), and on that non-coinjoin subsample measures: subjective-
signal COVERAGE, §04-fused vs graph-only entropy (SHARPENING), and the value_weighted ablation.

HONEST BIAS (stated in RESULTS): the resolved subsample excludes coinjoin-heavy coins — their
ancestry truncates because the exact subset-sum oracle can't evaluate dense mixes (the ceiling is the
oracle, not the data; a live proof found ~7/8 targets truncate on coinjoin parents). So this validates
§04 sharpening on non-coinjoin (peel-chain-ish) provenance, not the full population.

Subjective signal: address-reuse self-transfer — an input whose prevout address reappears as an
output address is same-owner with that output (pins the (input_i, output_j) link). Differentiates
inputs (unlike change-index, which only marks an output), so it can reweight the target's column.

usage: .venv/bin/python -m examples.anonymity_set_scale [max_tries] [need_resolved]
Live network; slow (throttled). Writes results/RESULTS-anonymity-set-scale.md.
"""
import os, sys, glob, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from decluster.fetch import fetch_tx
from decluster.ancestry import ancestry_entropy, build_extended_graph, absorber_distribution
from decluster.anonymity_set import provenance_anonymity_fused, sameowner_link_oracle, anonymity_bits
from examples.anonymity_set import hard_bounded_link_oracle

HERE = os.path.dirname(__file__)


def address_reuse_pairs(tx):
    """(input_i, output_j) where input i's prevout address == output j's address (self-transfer /
    reuse -> same-owner). Differentiates inputs, so it reweights the target output's link column."""
    ins = tx.get("vin", [])
    outs = tx.get("vout", [])
    pairs = set()
    for i, v in enumerate(ins):
        ia = v.get("prevout", {}).get("scriptpubkey_address")
        if not ia:
            continue
        for j, o in enumerate(outs):
            if o.get("scriptpubkey_address") == ia:
                pairs.add((i, j))
    return pairs


def seed_targets():
    """Real multi-input tx targets: cached tx dicts first (fast), then their inputs' parents (more)."""
    seen = set()
    out = []
    for p in glob.glob(os.path.join(HERE, "..", ".cache", "*.json")):
        txid = os.path.basename(p)[:-5]
        if len(txid) != 64 or txid in seen:
            continue
        try:
            tx = fetch_tx(txid)
        except Exception:
            continue
        if not isinstance(tx, dict):
            continue
        vin = tx.get("vin", [])
        # multi-input, not coinjoin-scale (dense mixes truncate), not coinbase
        if tx.get("vout") and 2 <= len(vin) <= 12 and not vin[0].get("is_coinbase"):
            seen.add(txid)
            out.append(txid)
    return out


def run(max_tries=200, need_resolved=20, depth=4):
    targets = seed_targets()
    rows = []
    resolved = 0
    tried = 0
    for txid in targets:
        if tried >= max_tries or resolved >= need_resolved:
            break
        tried += 1
        try:
            g = ancestry_entropy((txid, 0), depth=depth, fetch=fetch_tx,
                                 link_oracle=hard_bounded_link_oracle)
        except Exception:
            continue
        if g["n_absorbers"] < 2:      # collapsed / truncated -> not in the non-coinjoin subsample
            continue
        resolved += 1
        tx = fetch_tx(txid)
        pairs = address_reuse_pairs(tx)
        fired = bool(pairs)
        fused_bits = g["shannon"]
        if fired:
            oracle = sameowner_link_oracle(address_reuse_pairs)
            fdist = provenance_anonymity_fused((txid, 0), oracle, depth=depth, fetch=fetch_tx,
                                               link_oracle=hard_bounded_link_oracle)
            fused_bits = anonymity_bits(fdist)["shannon"]
        # value_weighted ablation (graph-only, satoshi-weighted walk)
        try:
            vg = build_extended_graph((txid, 0), depth=depth, fetch=fetch_tx,
                                      link_oracle=hard_bounded_link_oracle, value_weighted=True)
            vbits = anonymity_bits(absorber_distribution(vg, (txid, 0)))["shannon"]
        except Exception:
            vbits = None
        rows.append({"txid": txid, "inputs": len(tx.get("vin", [])), "absorbers": g["n_absorbers"],
                     "graph_bits": g["shannon"], "reuse_fired": fired, "fused_bits": fused_bits,
                     "value_weighted_bits": vbits})
        print(f"{txid[:12]} abs={g['n_absorbers']} graph={g['shannon']:.3f} "
              f"reuse={'Y' if fired else '-'} fused={fused_bits:.3f} vw={vbits}", flush=True)

    covered = [r for r in rows if r["reuse_fired"]]
    sharpened = [r for r in covered if r["fused_bits"] < r["graph_bits"] - 1e-9]
    summary = {
        "tried": tried, "resolved": len(rows), "resolve_rate": len(rows) / tried if tried else 0.0,
        "coverage": len(covered), "coverage_frac": len(covered) / len(rows) if rows else 0.0,
        "sharpened": len(sharpened),
        "mean_graph_bits": sum(r["graph_bits"] for r in rows) / len(rows) if rows else 0.0,
        "mean_fused_bits_covered": sum(r["fused_bits"] for r in covered) / len(covered) if covered else None,
        "mean_reduction_covered": (sum(r["graph_bits"] - r["fused_bits"] for r in covered) / len(covered))
                                  if covered else None,
    }
    out = {"summary": summary, "rows": rows}
    with open(os.path.join(HERE, "..", "results", "scale_output.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("\nSUMMARY:", json.dumps(summary, indent=2, default=str), flush=True)
    return out


if __name__ == "__main__":
    mt = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    nr = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    run(max_tries=mt, need_resolved=nr)
