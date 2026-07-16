"""Tx-level pre<->post change score: the FS Combiner agreement (bits) between T and each output's
onward-spending tx. This compares T to its output's spender — a construction-fingerprint signal
disjoint from the co-spend label — and feeds the per-axis / combined-AUC validation in
change_validate. `output_score` is the building block; a same-owner onward-spend tends to agree."""
from .fetch import fetch_tx, fetch_outspends

def spending_tx(tx, i, get_tx=fetch_tx, get_outspends=fetch_outspends):
    s = get_outspends(tx["txid"])[i]
    return get_tx(s["txid"]) if s.get("spent") else None

def output_score(tx, i, combiner, get_tx=fetch_tx, get_outspends=fetch_outspends):
    post = spending_tx(tx, i, get_tx, get_outspends)
    return None if post is None else combiner.score(tx, post)
