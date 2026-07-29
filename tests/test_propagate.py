from decluster.propagate import build_rarity


def test_build_rarity_counts_supports():
    sigs = [{"a": 0.6, "b": 0.4}, {"a": 1.0}, {"b": 0.5, "c": 0.5}]
    assert build_rarity(sigs) == {"a": 2, "b": 2, "c": 1}


def test_build_rarity_empty():
    assert build_rarity([]) == {}
