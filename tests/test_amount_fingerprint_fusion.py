"""End-to-end: the coinjoin de-mix bits and the fingerprint bits are fused in ONE engine
(`cluster_refined`). A small JoinMarket coinjoin (3 single-input makers A,B,C; mix 100 + far-apart
changes) with a fingerprint linking A,B. Without the amount channel the co-spend prior collapses all
inputs into one cluster; with it, the de-mix refuses the different-participant pairs and the makers
separate."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

CJ = {"txid": "T",
      "vin": [{"txid": "A", "prevout": {"value": 100099}},
              {"txid": "B", "prevout": {"value": 50099}},
              {"txid": "C", "prevout": {"value": 10099}}],
      "vout": [{"value": 100}, {"value": 100}, {"value": 100},
               {"value": 100000}, {"value": 50000}, {"value": 10000}]}


def _fetch(t):
    if t == "T":
        return CJ
    return {"txid": t, "vin": [{"txid": "seed_" + t, "prevout": {"value": 1}}], "vout": [{"value": 1}]}


class _FingerprintLinkAB:
    def score(self, a, b, explain=False):
        return 3.0 if {a["txid"], b["txid"]} == {"A", "B"} else 0.0


def _run(subsetsum):
    import decluster.cluster as cl
    orig = cl._cospent_pairs
    cl.fetch_tx = _fetch
    cl._cospent_pairs = lambda nodes: [("A", "B", "T"), ("A", "C", "T"), ("B", "C", "T")]
    try:
        groups = cl.cluster_refined(["A", "B", "C"], _FingerprintLinkAB(),
                                    amount=False, link_above=99, subsetsum=subsetsum)[0]
        return sorted(sorted(g) for g in groups)
    finally:
        cl._cospent_pairs = orig


def test_cospend_and_fingerprint_alone_collapse_the_coinjoin():
    assert _run(subsetsum=False) == [["A", "B", "C"]]


def test_demix_and_fingerprint_bits_fuse_in_one_engine():
    # the de-mix assigns A,B,C to different participants -> refuses every pair -> makers separate.
    assert _run(subsetsum=True) == [["A"], ["B"], ["C"]]
