"""Canonical result artifacts and side-effect-free identity verification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .data_manifest import ContentIdentity, RunManifest


class OutputStatus(str, Enum):
    VERIFIED = "verified"
    MISSING = "missing"
    IDENTITY_MISMATCH = "identity_mismatch"


@dataclass(frozen=True)
class OutputVerification:
    path: str
    status: OutputStatus
    expected: ContentIdentity
    actual: ContentIdentity | None


def canonical_json_bytes(value) -> bytes:
    """Serialize JSON deterministically, rejecting values JSON cannot represent exactly."""
    return (json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ) + "\n").encode("utf-8")


def write_canonical_json(path, value) -> ContentIdentity:
    """Atomically replace ``path`` with canonical JSON and return its content identity."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(value)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
        temporary.write(payload)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    try:
        os.replace(temporary_path, destination)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return ContentIdentity(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())


def content_identity(path) -> ContentIdentity:
    source = Path(path)
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return ContentIdentity(bytes=size, sha256=digest.hexdigest())


def verify_run_outputs(manifest: RunManifest, root) -> tuple[OutputVerification, ...]:
    """Verify declared output identities without executing the manifest's commands."""
    root = Path(root).resolve()
    checks = []
    for output in manifest.outputs:
        expected = ContentIdentity(bytes=output.bytes, sha256=output.sha256)
        path = root / output.path
        if not path.is_file():
            checks.append(OutputVerification(
                path=output.path, status=OutputStatus.MISSING,
                expected=expected, actual=None,
            ))
            continue
        actual = content_identity(path)
        status = OutputStatus.VERIFIED if actual == expected else OutputStatus.IDENTITY_MISMATCH
        checks.append(OutputVerification(
            path=output.path, status=status, expected=expected, actual=actual,
        ))
    return tuple(checks)
