from decluster.propagate import build_rarity, entity_signature


def test_build_rarity_counts_supports():
    sigs = [{"a": 0.6, "b": 0.4}, {"a": 1.0}, {"b": 0.5, "c": 0.5}]
    assert build_rarity(sigs) == {"a": 2, "b": 2, "c": 1}


def test_build_rarity_empty():
    assert build_rarity([]) == {}


def test_entity_signature_sums_and_normalises():
    sig = entity_signature([{"a": 0.5, "b": 0.5}, {"a": 0.5, "c": 0.5}])
    # summed: a=1.0, b=0.5, c=0.5 (total 2.0) -> normalised
    assert sig == {"a": 0.5, "b": 0.25, "c": 0.25}


def test_entity_signature_empty():
    assert entity_signature([]) == {}
    assert entity_signature([{}, {}]) == {}
