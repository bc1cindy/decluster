"""The two address readings every view construction starts from.

Clustering, the partition schemes and contraction all read a transaction the same way. Kept here
rather than in any one of them because a private copy in one is the copy the other two quietly
diverge from.
"""


def in_addrs(tx):
    return [a for a in (v.get("prevout", {}).get("scriptpubkey_address")
                        for v in tx.get("vin", [])) if a]


def out_addrs(tx):
    return [(o.get("scriptpubkey_address"), o.get("value") or 0)
            for o in tx.get("vout", []) if o.get("scriptpubkey_address")]
