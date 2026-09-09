import io
import json
from pathlib import Path
import tarfile

import pytest

from decluster.archive_snapshot import UnsafeArchiveError, extract_tar_gz
from decluster.experiments import fs_temporal as experiment

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "fs-blkcache-2026-09-04.tar.gz"


@pytest.mark.canonical
def test_snapshot_reproduces_the_historical_report():
    historical = json.loads((ROOT / "results" / "fs-temporal.json").read_text())
    artifact = experiment.build_artifact(SNAPSHOT)

    assert artifact["report"] == historical
    assert artifact["dataset"] == "fs-blkcache-2026-09-04-v1"


def test_verifier_recomputes_the_population_result():
    artifact = experiment.build_artifact(SNAPSHOT)
    artifact["report"]["fellegi_sunter"]["auc"] = 1.0

    with pytest.raises(experiment.VerificationError, match="fresh experiment"):
        experiment.verify_artifact(artifact, SNAPSHOT)


def test_archive_extraction_rejects_path_traversal(tmp_path):
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as target:
        member = tarfile.TarInfo("../escape")
        member.size = 1
        target.addfile(member, io.BytesIO(b"x"))

    with pytest.raises(UnsafeArchiveError, match="unsafe archive path"):
        extract_tar_gz(archive, tmp_path / "output")
