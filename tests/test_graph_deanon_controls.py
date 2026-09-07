"""The graph-structure headline, its control, and the determinism both depend on."""
import json
import subprocess
import sys

import pytest

from decluster.experiments import graph_deanon_controls as experiment


@pytest.fixture(scope="module")
def artifact():
    return experiment.build_artifact()


def test_reproduce_then_verify(tmp_path):
    art, markdown = tmp_path / "a.json", tmp_path / "a.md"
    assert experiment.main(["reproduce", "--artifact", str(art), "--markdown", str(markdown)]) == 0
    assert experiment.main(["verify", "--artifact", str(art), "--markdown", str(markdown)]) == 0


def test_the_run_is_the_same_in_a_second_process():
    """A seeded run whose population order came out of a set answered differently every time.

    Three processes gave 0.9905, 0.9908 and 0.9910 for the same fixture and the same seed, which is
    why the AUC this fixture carries had no canonical run behind it.
    """
    script = (
        "import json;"
        "from decluster.experiments import graph_deanon_controls as e;"
        "a=e.build_artifact();"
        "print(json.dumps(a['measurement']['views'], sort_keys=True))"
    )
    first, second = (
        subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
        for _ in range(2)
    )
    assert first.stdout == second.stdout


def test_the_degree_only_score_is_at_chance_under_matching(artifact):
    payment = artifact["measurement"]["views"]["payment"]
    assert payment["degree_only_auc_under_matching"] == pytest.approx(0.5, abs=0.01)


def test_the_shuffled_label_control_is_at_chance(artifact):
    assert artifact["measurement"]["shuffled_label_auc"] == pytest.approx(0.5, abs=0.01)


def test_the_headline_falls_under_the_control_and_the_fall_is_reported(artifact):
    for view in artifact["measurement"]["views"].values():
        assert view["fall_under_matching"] > 0
        assert view["degree_matched_auc"] < view["published_auc"]


def test_a_tampered_artifact_is_refused(artifact):
    stored = json.loads(json.dumps(artifact))
    stored["measurement"]["views"]["payment"]["published_auc"] += 0.01
    with pytest.raises(experiment.VerificationError):
        experiment.verify_artifact(stored)
