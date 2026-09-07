"""p_II is what the co-spend heuristic asserts; these pin what it does and does not mean."""
import json

import pytest

from decluster.baselines import boltzmann
from decluster.experiments import same_block_linkage as experiment


@pytest.fixture(scope="module")
def artifact():
    return experiment.build_artifact()


def test_reproduce_then_verify(tmp_path):
    art, markdown = tmp_path / "a.json", tmp_path / "a.md"
    assert experiment.main(["reproduce", "--artifact", str(art), "--markdown", str(markdown)]) == 0
    assert experiment.main(["verify", "--artifact", str(art), "--markdown", str(markdown)]) == 0


def test_the_diagonal_is_not_counted_as_a_pair(artifact):
    # Every coin shares its own block, so counting the diagonal would report p_II = 1 for free.
    measured = artifact["measurement"]
    assert measured["input_pairs"] < sum(
        count for count in measured["p_ii_distribution"].values()
    ) + 1
    assert measured["input_pairs"] == sum(measured["p_ii_distribution"].values())


def test_p_ii_is_the_same_side_quantity():
    """Two inputs of a transaction whose amounts admit two readings are not forced together."""
    analysis = boltzmann.same_block_probabilities([4, 6], [4, 6], max_coins=12)
    assert analysis.mapping_count
    assert analysis.input_matrix[0][1] < 1.0


def test_a_transaction_the_amounts_cannot_split_forces_its_inputs():
    analysis = boltzmann.same_block_probabilities([3, 5], [8], max_coins=12)
    assert analysis.mapping_count
    assert analysis.input_matrix[0][1] == 1.0


def test_the_forced_share_is_reported_with_both_directions(artifact):
    measured = artifact["measurement"]
    assert measured["input_pairs_forced_together"] > 0
    assert "input_pairs_forced_apart" in measured
    assert measured["input_pairs_forced_together"] <= measured["input_pairs"]


def test_a_tampered_artifact_is_refused(artifact):
    stored = json.loads(json.dumps(artifact))
    stored["measurement"]["input_pairs_forced_together"] += 1
    with pytest.raises(experiment.VerificationError):
        experiment.verify_artifact(stored)
