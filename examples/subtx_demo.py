"""Amount ALONE re-partitions merged transaction 931d6627 (before any fingerprint)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decluster.fetch import fetch_tx
from decluster.subtransaction import subtransactions, partition_signal

MERGE = "931d6627f7b63491cbc2e6d860dc630537385fd9ee3171f2013b64e6a143a4e4"

if __name__ == "__main__":
    t = fetch_tx(MERGE)
    tx = {"txid": MERGE,
          "vin": [{"txid": v["txid"], "prevout": {"value": v["prevout"]["value"]}} for v in t["vin"]],
          "vout": [{"value": o["value"]} for o in t["vout"]]}
    ranked, amb = subtransactions(tx)
    print(f"merged transaction {MERGE[:10]}..  ambiguity = {amb} bits ({len(ranked)} particoes balanceadas)")
    for payment, score, ri, ro in ranked:
        print(f"  payment={payment:>6}  roundness={score}  receiver=in{ri}->out{ro}")
    sig = partition_signal(tx)
    print("\nmais provavel:")
    print("  REFUSE (donos diferentes):", sig["refuse"])
    print("  LINK   (input->output):   ", sig["link"])
    print(f"  payment implicito = {sig['payment']}")
