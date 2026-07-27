"""Coherent, refuse-only entity guards wired into the engine's topology stage: the super-cluster guard
(a known hub never corroborates a merge) and the dust guard (a dust spray's edges are not counterparty
structure). Both can only REMOVE a spurious link, never add one — the framework's boundary-condition
role for entity labels, not label-driven clustering."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.cluster import counterparty_bits
from decluster.graph_deanon import build

def test_supercluster_guard_zeros_known_hub_only():
    # ENT and rare are each touched by 2 of 4 nodes -> equal measured rarity (1 bit) without the guard
    neigh = {"A": {"ENT"}, "B": {"ENT"}, "C": {"rare"}, "D": {"rare"}}
    b0 = counterparty_bits(neigh)
    assert b0["ENT"] == b0["rare"] > 0
    b1 = counterparty_bits(neigh, hubs={"ENT"})
    assert b1["ENT"] == 0.0                       # known super-cluster forced to hub -> cannot corroborate
    assert b1["rare"] == b0["rare"]               # everything else untouched
    # a known hub not present in the graph is simply ignored (no crash, no spurious key)
    assert "MISSING" not in counterparty_bits(neigh, hubs={"MISSING"})

def _dust_tx():
    return {"vin": [{"prevout": {"scriptpubkey_address": "1duster"}}],
            "vout": [{"value": 546, "scriptpubkey_address": f"1victim{i}"} for i in range(25)]}

def test_dust_guard_drops_fanout_counterparty_edges():
    sample = [(_dust_tx(), None)]
    _, _, neigh_pay, _ = build(sample, dust_guard=False)
    assert len(neigh_pay.get("1duster", set())) == 25       # without guard: duster is a false shared counterparty of 25 victims
    _, _, neigh_pay_g, _ = build(sample, dust_guard=True)
    assert "1duster" not in neigh_pay_g                      # with guard: the dust edges are gone
    assert not any(k.startswith("1victim") for k in neigh_pay_g)

def test_entity_hub_addresses_collects_supercluster_seeds():
    from decluster.entities import entity_hub_addresses
    txs = [{"vout": [{"value": 1, "scriptpubkey_type": "p2pkh", "scriptpubkey_address": "1dice8EMZ"}], "vin": []},
           {"vout": [{"value": 1, "scriptpubkey_type": "p2sh", "scriptpubkey_address": "3BMEXaa"}], "vin": []}]
    hubs = entity_hub_addresses(txs, curated={"1GoxAddr": {"kind": "supercluster"}, "1priv": {"kind": "other"}})
    assert "1dice8EMZ" in hubs and "3BMEXaa" in hubs      # detector-derived service addresses
    assert "1GoxAddr" in hubs and "1priv" not in hubs      # curated super-clusters only

def test_dust_guard_keeps_ordinary_payments():
    ordinary = {"vin": [{"prevout": {"scriptpubkey_address": "1payer"}}],
                "vout": [{"value": 500000, "scriptpubkey_address": "1payee"},
                         {"value": 12000, "scriptpubkey_address": "1change"}]}
    _, _, ng, _ = build([(ordinary, None)], dust_guard=True)
    assert "1payer" in ng and "1payee" in ng["1payer"]      # a normal 2-output payment is untouched by the guard

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
