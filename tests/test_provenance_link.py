"""Deep-feature matching: two coins are linked by the OVERLAP of their provenance signatures (the
sparse ancestral-boundary distribution), a Narayanan-Shmatikov quasi-identifier. A shared *rare*
ancestor is strong same-origin evidence; a shared hub (a coinbase everyone descends from) is weak."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.ancestry import (ancestry_signature, provenance_link,
                                 build_extended_graph, absorber_distribution, dss_link_oracle)

def test_provenance_link_shared_vs_disjoint():
    a = {("O", 0): 0.6, ("P", 0): 0.4}
    b = {("O", 0): 0.5, ("Q", 0): 0.5}
    c = {("R", 0): 1.0}
    assert provenance_link(a, b) == 0.5          # shared ancestor O: min(0.6, 0.5)
    assert provenance_link(a, c) == 0.0          # disjoint provenance -> no link
    assert provenance_link(a, a) == 1.0          # identical signature -> full overlap

def test_provenance_link_rarity_downweights_hubs():
    a = {("HUB", 0): 0.5, ("RARE", 0): 0.5}
    b = {("HUB", 0): 0.5, ("RARE", 0): 0.5}
    rarity = {("HUB", 0): 1000, ("RARE", 0): 2}
    unweighted = provenance_link(a, b)                       # 0.5 + 0.5 = 1.0
    weighted = provenance_link(a, b, rarity)                 # hub ~0, rare dominates
    assert weighted < unweighted
    # rare wt = 1/log2(3) ≈ 0.63 ; hub wt = 1/log2(1001) ≈ 0.10
    assert abs(weighted - (0.5 / math.log2(3) + 0.5 / math.log2(1001))) < 1e-9

def _fetch(txs):
    return lambda t: txs[t]

def test_ancestry_signature_is_absorber_distribution():
    # C.vout0 = 3 sats comes from input P:0 (also 3); its provenance signature is the atom {P:0: 1.0}
    txs = {
        "C": {"vin": [{"is_coinbase": False, "txid": "P", "vout": 0, "prevout": {"value": 3}},
                      {"is_coinbase": False, "txid": "R", "vout": 0, "prevout": {"value": 5}}],
              "vout": [{"value": 3}, {"value": 5}]},
        "P": {"vin": [{"is_coinbase": True, "prevout": None}], "vout": [{"value": 3}]},
        "R": {"vin": [{"is_coinbase": True, "prevout": None}], "vout": [{"value": 5}]},
    }
    sig0 = ancestry_signature(("C", 0), depth=6, fetch=_fetch(txs), link_oracle=dss_link_oracle)
    sig1 = ancestry_signature(("C", 1), depth=6, fetch=_fetch(txs), link_oracle=dss_link_oracle)
    assert sig0 == {("P", 0): 1.0} and sig1 == {("R", 0): 1.0}
    # the matching attack: C.vout0 and a sibling also sourced from P:0 would link; C.vout1 would not
    assert provenance_link(sig0, sig0) == 1.0
    assert provenance_link(sig0, sig1) == 0.0        # different origins -> no provenance link

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
