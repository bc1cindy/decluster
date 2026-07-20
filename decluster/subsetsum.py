"""Amount channel: the per-pair de-mix refuse (`amount_refuse_demix`) the clusterer consumes. Two
co-spent inputs assigned to different coinjoin participants (via `coinjoin_demix`) are conclusively
different owners."""
from .coinjoin_demix import coinjoin_demix

DEMIX_REFUSE_BITS = -12.0          # a conclusive de-mix separation -> strong refuse; dominates cospend + fp


def amount_refuse_demix(tx, a, b):
    """Weight for co-spent funders a,b of a coinjoin `tx`: DEMIX_REFUSE_BITS when the de-mix assigns them
    to different participants (conclusively different owners), else 0.0. a,b are funder txids mapped to
    their input indices. Abstains unless both are funders and every input carries a prevout value."""
    funders = [v.get("txid") for v in tx.get("vin", [])]
    ins = [v["prevout"]["value"] for v in tx.get("vin", []) if "prevout" in v]
    outs = [o["value"] for o in tx.get("vout", [])]
    if a not in funders or b not in funders or len(ins) != len(funders):
        return 0.0
    i_a, i_b = funders.index(a), funders.index(b)
    assign = coinjoin_demix(ins, outs)
    if i_a in assign and i_b in assign and assign[i_a] != assign[i_b]:
        return DEMIX_REFUSE_BITS
    return 0.0
