"""Optimal-change (UIH, cit-15/16) wiring into cluster_addresses, collapse-safe (fresh change only)."""
from decluster.views import cluster_addresses


def _tx(ins_val, outs, height=0):
    # ins_val: [(addr,value)], outs: [(addr,value)]
    return ({"height": height,
             "vin": [{"prevout": {"scriptpubkey_address": a, "value": v}} for a, v in ins_val],
             "vout": [{"scriptpubkey_address": a, "value": v} for a, v in outs]}, 0)


def test_change_link_merges_fresh_change_only_when_enabled():
    prior = _tx([("in1", 60), ("in2", 60)], [("prior_out", 110)])
    tx = _tx([("in1", 100), ("in2", 100)], [("change", 50), ("pay", 140)])  # change=out0 (<100)
    no = cluster_addresses([prior, tx], change_link=False)
    yes = cluster_addresses([prior, tx], change_link=True)
    assert "change" not in no                       # off: change stays an unlinked output
    assert yes["change"] == yes["in1"]              # on: fresh change joins the input cluster


def test_change_link_skips_non_fresh_change_collapse_guard():
    # 'shared' is used as an input elsewhere -> not fresh -> linking it could collapse clusters
    tx1 = _tx([("in1", 100), ("in2", 100)], [("shared", 50), ("pay", 140)])
    tx2 = _tx([("shared", 30), ("other", 30)], [("z", 55)])   # 'shared' appears as an input
    yes = cluster_addresses([tx1, tx2], change_link=True)
    # 'shared' clusters with tx2's inputs (co-spend), NOT pulled into tx1's input cluster
    assert yes.get("shared") != yes.get("in1")


def test_change_link_abstains_without_prior_same_owner_evidence():
    # A two-party interpretation is possible. Input order must not assign the small output to
    # whichever input appears first when no independent evidence links the inputs.
    tx = _tx([("alice", 10), ("bob", 100)], [("alice_out", 9), ("bob_out", 90)])
    forward = cluster_addresses([tx], change_link=True)
    reverse_tx = _tx([("bob", 100), ("alice", 10)], [("alice_out", 9), ("bob_out", 90)])
    reverse = cluster_addresses([reverse_tx], change_link=True)
    assert "alice_out" not in forward and "alice_out" not in reverse
