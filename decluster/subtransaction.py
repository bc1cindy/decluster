"""Structural layer — amount inference (subtransaction/UIH) that re-partitions a 2-in/2-out
merged transaction. This is the PRIMARY signal; the fingerprint corroborates. In
2-in/2-out the per-owner balance is automatic, so the discriminator is the roundness of the
implied payment (receiver's output minus the input it contributed)."""
import math

def roundness(x):
    """how 'designed' the number looks: +k if divisible by 10^k (1000 -> 3, 4750 -> 1)."""
    if x <= 0: return 0
    k = 0
    while x % 10 == 0:
        x //= 10; k += 1
    return k

def subtransactions(tx):
    """balanced 2-owner partitions of a 2-in/2-out merged transaction, ranked by plausibility.
    Returns (ranked, ambiguity_bits); ranked = [(payment, score, r_in_idx, r_out_idx)]."""
    ins = [(i, v["prevout"]["value"]) for i, v in enumerate(tx["vin"])]
    outs = [(j, o["value"]) for j, o in enumerate(tx["vout"])]
    if len(ins) != 2 or len(outs) != 2:
        return [], None                      # scope guard: v1 is 2-in/2-out only
    plausible = []
    for ri, vr in ins:
        for ro, wr in outs:
            payment = wr - vr                # receiver adds its input to the payment
            if payment <= 0:
                continue
            plausible.append((payment, roundness(payment), ri, ro))
    plausible.sort(key=lambda t: (-t[1], -t[0]))
    amb = math.log2(len(plausible)) if plausible else None
    return plausible, amb

def partition_signal(tx):
    """structural signal for the combiner: refuse (different-owner inputs) + link
    (input -> its output) from the most likely partition. scope guard -> empty."""
    ranked, amb = subtransactions(tx)
    if not ranked:
        return {"refuse": [], "link": [], "payment": None, "ambiguity_bits": amb}
    payment, _score, ri, ro = ranked[0]
    txids = [v["txid"] for v in tx["vin"]]
    si = next(i for i in range(2) if i != ri)
    so = next(j for j in range(2) if j != ro)
    return {
        "refuse": [(txids[si], txids[ri])],                         # different owners
        "link": [(txids[ri], f"{tx['txid']}:{ro}"),                 # receiver -> its output
                 (txids[si], f"{tx['txid']}:{so}")],                # sender -> its output
        "payment": payment,
        "ambiguity_bits": amb,
    }
