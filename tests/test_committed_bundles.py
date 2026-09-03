from pathlib import Path

from decluster.evidence_bundle import BlobStatus, load_bundle, verify_bundle


ROOT = Path(__file__).resolve().parents[1]


def test_every_committed_bundle_is_complete_and_content_verified():
    indexes = sorted((ROOT / "releases").glob("*.bundle.json"))
    assert indexes, "no evidence bundle is committed"
    for index in indexes:
        bundle = load_bundle(index)
        checks = verify_bundle(bundle, ROOT / "artifacts")
        failures = [check for check in checks if check.status is not BlobStatus.VERIFIED]
        assert not failures, f"{index}: {failures}"
