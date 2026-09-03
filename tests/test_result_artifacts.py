import hashlib
import json

import pytest

from decluster.data_manifest import (
    ContentIdentity,
    RunManifest,
    RunOutput,
    RunVerification,
    ReproducibilityLevel,
    RunAvailability,
    VerificationMode,
)
from decluster.result_artifacts import (
    OutputStatus,
    canonical_json_bytes,
    verify_run_outputs,
    write_canonical_json,
)


def manifest_for(path, payload):
    return RunManifest(
        id="run", claim_ids=("claim",), code_revision="abc", dirty=False,
        argv=("run",), python="3.13", lock_digest=None, platform="any", dependencies=(),
        datasets=(), parameters={}, rng_algorithm=None, rng_seeds=(),
        outputs=(RunOutput(
            path=path,
            bytes=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
        ),),
        reproducibility_level=ReproducibilityLevel.BITWISE,
        availability=RunAvailability.COMPLETE,
        verification=RunVerification(
            mode=VerificationMode.EXACT, argv=("verify",), tests=(),
            properties=("content identity",), tolerance=None,
        ),
        limitations=(),
    )


def test_canonical_json_is_stable_and_rejects_non_finite_numbers():
    assert canonical_json_bytes({"b": 2, "a": [1]}) == b'{"a":[1],"b":2}\n'
    with pytest.raises(ValueError):
        canonical_json_bytes({"value": float("nan")})


def test_atomic_writer_returns_the_written_identity(tmp_path):
    path = tmp_path / "nested" / "result.json"
    identity = write_canonical_json(path, {"answer": 42})
    assert path.read_bytes() == b'{"answer":42}\n'
    assert identity == ContentIdentity(
        bytes=14,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def test_output_verification_distinguishes_verified_missing_and_mismatch(tmp_path):
    payload = canonical_json_bytes({"answer": 42})
    path = tmp_path / "result.json"
    path.write_bytes(payload)
    manifest = manifest_for("result.json", payload)

    assert verify_run_outputs(manifest, tmp_path)[0].status is OutputStatus.VERIFIED
    path.write_text(json.dumps({"answer": 41}))
    assert verify_run_outputs(manifest, tmp_path)[0].status is OutputStatus.IDENTITY_MISMATCH
    path.unlink()
    check = verify_run_outputs(manifest, tmp_path)[0]
    assert check.status is OutputStatus.MISSING
    assert check.actual is None
