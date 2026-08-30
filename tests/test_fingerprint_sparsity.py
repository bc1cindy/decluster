import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from examples.fingerprint_sparsity import bucket, distribution, LABELS


def test_bucket_boundaries():
    assert bucket(1) == "exactly 1"
    assert bucket(2) == "2-9" and bucket(9) == "2-9"
    assert bucket(10) == "10-99" and bucket(99) == "10-99"
    assert bucket(100) == "100-999" and bucket(999) == "100-999"
    assert bucket(1_000) == "1,000-9,999"
    assert bucket(10_000) == "10,000-99,999"
    assert bucket(99_999) == "10,000-99,999"
    assert bucket(100_000) == ">=100,000"


def test_shares_weight_transactions_not_vectors():
    """One vector of 90 txs and nine singletons: 90% of TRANSACTIONS sit in the large
    class even though 90% of VECTORS are singletons. Weighting by vector would invert it."""
    counts = {"big": 90, **{f"s{i}": 1 for i in range(9)}}
    dist, total = distribution(counts)
    assert total == 99
    assert dist["exactly 1"] == 9 / 99
    assert dist["10-99"] == 90 / 99


def test_distribution_is_complete_and_normalised():
    counts = {"a": 1, "b": 5, "c": 150, "d": 250_000}
    dist, total = distribution(counts)
    assert total == sum(counts.values())
    assert set(dist) == set(LABELS)
    assert abs(sum(dist.values()) - 1.0) < 1e-12
