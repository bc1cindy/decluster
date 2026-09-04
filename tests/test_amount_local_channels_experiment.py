import json

import pytest

from decluster.experiments import amount_local_channels as experiment


def test_report_preserves_published_local_channel_counts():
    report = experiment.build_report()

    assert report["population"]["transactions"] == 5491
    assert report["population"]["multi_input"] == 1428
    assert report["coinjoin"] == {"shape_detected": 28, "demixed": 0}
    assert report["unnecessary_input"]["fires"] == 485
    assert report["subtransaction_roundness"] == {"ranked": 483, "top_tied": 330}


def test_artifact_excludes_dss_and_composition_claims():
    limitations = experiment.build_artifact()["limitations"]

    assert "largest input" in limitations[3]
    assert "excludes subset-sum, DSS" in limitations[4]


def test_verifier_rejects_changed_measurement():
    changed = json.loads(json.dumps(experiment.build_artifact()))
    changed["report"]["coinjoin"]["demixed"] = 1

    with pytest.raises(experiment.VerificationError, match="fresh experiment"):
        experiment.verify_artifact(changed)
