from decluster.propagate import build_rarity, entity_signature, label_scores, eccentricity


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


def test_label_scores_uses_provenance_link():
    node = {"rare": 0.5, "hub": 0.5}
    labels = {"X": {"rare": 0.5, "hub": 0.5}, "Y": {"hub": 1.0}}
    rarity = {"rare": 1, "hub": 100}   # rare ancestor weighs more
    s = label_scores(node, labels, rarity)
    assert s["X"] > s["Y"] > 0.0


def test_eccentricity_gap_over_spread():
    # best 10, second 2, third 0 -> clear separation, positive eccentricity
    assert eccentricity({"a": 10.0, "b": 2.0, "c": 0.0}) > 0.0


def test_eccentricity_degenerate():
    assert eccentricity({"a": 5.0}) == 0.0          # <2 scores
    assert eccentricity({"a": 3.0, "b": 3.0}) == 0.0  # zero spread
