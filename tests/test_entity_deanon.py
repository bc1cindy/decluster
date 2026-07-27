"""The entity-label probe is the INDEPENDENT-label unlock for the strong Narayanan-Shmatikov claim:
an entity detector (here BitMEX vanity addresses) groups addresses that co-spend leaves separate, and
payment-graph structure then re-links them. This tests the mechanism on a controlled synthetic graph
(the real-mainnet AUC needs an entity-covered connected slice, which the repo's samples lack)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.graph_deanon import entity_label_uf, evaluate_entity
from decluster.entities import detect_bitmex

def _sweep(dep_addr, hot):
    """A BitMEX-style sweep: the deposit (a 3BMEX… input) is swept to the hot wallet `hot`. Two such
    sweeps share `hot` as a payment counterparty WITHOUT co-spending the two deposits."""
    return {"txid": "sw_" + dep_addr, "vin": [{"txid": "f_" + dep_addr, "vout": 0,
             "prevout": {"scriptpubkey_address": dep_addr}}],
            "vout": [{"value": 100, "scriptpubkey_type": "p2sh", "scriptpubkey_address": hot}]}

def test_entity_label_is_independent_of_cospend():
    # two BitMEX deposits, each swept in its OWN tx -> never co-spent, but same entity
    sample = [(_sweep("3BMEXaaa", "hotwallet"), None), (_sweep("3BMEXbbb", "hotwallet"), None)]
    uf, anchors = entity_label_uf(sample, detect_bitmex)
    assert uf.find("3BMEXaaa") == uf.find("3BMEXbbb")           # grouped by entity, though never co-spent
    assert uf.find("3BMEXaaa") != uf.find("hotwallet")          # non-entity addr stays separate

def test_structure_relinks_what_cospend_leaves_separate():
    # entity pair shares the hot-wallet counterparty (structural link); a control address shares nothing
    sample = [(_sweep("3BMEXaaa", "hotwallet"), None),
              (_sweep("3BMEXbbb", "hotwallet"), None),
              ({"txid": "ctl", "vin": [{"txid": "fc", "vout": 0, "prevout": {"scriptpubkey_address": "1control"}}],
                "vout": [{"value": 100, "scriptpubkey_type": "p2pkh", "scriptpubkey_address": "1elsewhere"}]}, None)]
    r = evaluate_entity(sample, detect_bitmex)
    assert r["entity_clusters"] == 1 and r["pos_pairs"] == 1
    assert r["pos_mean"] >= 1.0                                 # the held-out same-entity pair shares >=1 neighbor
    assert r["auc_payment"] is not None and r["auc_payment"] > 0.5

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
