"""Pin the gist's most-emphasised attack (wallet-fingerprint clustering is "extremely powerful",
Collaborative-Transaction-Privacy cit 21-23) on committed real data: a frozen 600-tx witness-bearing
sample of the `.blkcache` (`tests/fixtures/fingerprint_blkcache_sample.json`). The canonical
library scorer separates same-owner (address-reuse label) pairs from random pairs. The chain-scale
number in `results/RESULTS-fingerprint-validation.md` (AUC ~0.93) is a population statistic that a
small sample cannot reproduce exactly; what is pinned is the load-bearing claim as a band — strong
separation, and a shuffle control at chance — reproducibly from the repo."""
import json
import os

from decluster.fingerprint_validate import evaluate, LibraryScorer

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "fingerprint_blkcache_sample.json")


def _txs():
    with open(FIX) as f:
        return json.load(f)


def test_fingerprint_scorer_separates_same_owner_from_random():
    r = evaluate(_txs(), LibraryScorer(), cap=4000, seed=0)
    assert r["n_pos"] > 100 and r["n_neg"] > 100
    assert r["auc"] >= 0.88                      # strongly above chance (doc ~0.93; this sample 0.95)
    assert 0.40 <= r["shuffle_auc"] <= 0.60       # label-shuffled control sits at chance
    assert r["pos_mean"] > 0 > r["neg_mean"]      # same-owner pairs score positive bits, random negative


def test_ns_form_signature_matching_also_separates():
    """The Narayanan-Shmatikov signature form (fingerprint vectors matched pairwise, cit 24) reaches
    the same regime on the committed sample: strong AUC, reproducibly."""
    from decluster.fingerprint_validate import reuse_pairs
    from decluster.fingerprint_ns import pairwise_auc, axis_fns, library_weights
    pos, neg = reuse_pairs(_txs(), cap=2000, seed=0)
    auc = pairwise_auc(pos, neg, axis_fns(), library_weights(), seed=0)
    assert auc >= 0.85                            # doc fingerprint-regime NS/FS AUC ~0.89-0.93
