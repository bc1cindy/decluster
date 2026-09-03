"""Content-addressed, offline evidence bundles.

An index names immutable blobs.  Verification never downloads, repairs or
executes anything; reproduction is a separate capability that an index must
declare only after its complete environment has been bundled.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
import shutil
import tempfile

from .data_manifest import ContentIdentity, ManifestError, SHA256
from .result_artifacts import content_identity


class BundleCapability(str, Enum):
    VERIFY_OUTPUTS = "verify_outputs"
    REPRODUCE_RUNS = "reproduce_runs"


class BlobRole(str, Enum):
    RUN_MANIFEST = "run_manifest"
    DATASET = "dataset"
    RESULT = "result"
    SOURCE = "source"
    DEPENDENCY = "dependency"
    LOCKFILE = "lockfile"
    ENVIRONMENT = "environment"


class BlobStatus(str, Enum):
    VERIFIED = "verified"
    MISSING = "missing"
    IDENTITY_MISMATCH = "identity_mismatch"


@dataclass(frozen=True)
class BundleBlob:
    name: str
    role: BlobRole
    content: ContentIdentity


@dataclass(frozen=True)
class EvidenceBundle:
    id: str
    capabilities: tuple[BundleCapability, ...]
    runs: tuple[str, ...]
    blobs: tuple[BundleBlob, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class BlobVerification:
    blob: BundleBlob
    status: BlobStatus
    actual: ContentIdentity | None


def blob_path(store, sha256: str) -> Path:
    if not SHA256.fullmatch(sha256):
        raise ValueError("expected lowercase SHA-256")
    return Path(store) / "sha256" / sha256[:2] / sha256[2:]


def ingest_blob(source, store) -> ContentIdentity:
    """Atomically add a file to a content-addressed store without overwriting it."""
    source = Path(source)
    identity = content_identity(source)
    destination = blob_path(store, identity.sha256)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if content_identity(destination) != identity:
            raise OSError(f"corrupt blob already exists: {destination}")
        return identity
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
        with source.open("rb") as stream:
            shutil.copyfileobj(stream, temporary)
        temporary.flush()
        os.fsync(temporary.fileno())
    try:
        if content_identity(temporary_path) != identity:
            raise OSError("source changed while being ingested")
        os.replace(temporary_path, destination)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return identity


def load_bundle(path) -> EvidenceBundle:
    where = str(path)
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"{where}: cannot read bundle: {exc}") from exc
    required = {"schema_version", "id", "capabilities", "runs", "blobs", "limitations"}
    if not isinstance(raw, dict) or set(raw) != required or raw.get("schema_version") != 1:
        raise ManifestError(f"{where}: invalid bundle envelope")

    def unique_texts(value, field):
        if not isinstance(value, list) or not value or any(not isinstance(x, str) or not x for x in value):
            raise ManifestError(f"{where}.{field}: expected non-empty string array")
        if len(value) != len(set(value)):
            raise ManifestError(f"{where}.{field}: duplicate value")
        return tuple(value)

    try:
        capabilities = tuple(BundleCapability(x) for x in unique_texts(raw["capabilities"], "capabilities"))
    except ValueError as exc:
        raise ManifestError(f"{where}.capabilities: invalid capability") from exc
    runs = unique_texts(raw["runs"], "runs")
    limitations = tuple(raw["limitations"])
    if any(not isinstance(x, str) or not x for x in limitations):
        raise ManifestError(f"{where}.limitations: expected string array")
    blobs = []
    names = set()
    identities = set()
    for index, item in enumerate(raw["blobs"]):
        item_where = f"{where}.blobs[{index}]"
        if not isinstance(item, dict) or set(item) != {"name", "role", "bytes", "sha256"}:
            raise ManifestError(f"{item_where}: invalid blob")
        name, digest, size = item["name"], item["sha256"], item["bytes"]
        if not isinstance(name, str) or not name or name in names:
            raise ManifestError(f"{item_where}.name: invalid or duplicate")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ManifestError(f"{item_where}.bytes: expected non-negative integer")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise ManifestError(f"{item_where}.sha256: expected lowercase SHA-256")
        try:
            role = BlobRole(item["role"])
        except ValueError as exc:
            raise ManifestError(f"{item_where}.role: invalid role") from exc
        identity = (size, digest)
        if identity in identities:
            raise ManifestError(f"{item_where}: duplicate content identity")
        names.add(name)
        identities.add(identity)
        blobs.append(BundleBlob(name, role, ContentIdentity(size, digest)))
    if not blobs:
        raise ManifestError(f"{where}.blobs: expected non-empty array")
    roles = {blob.role for blob in blobs}
    if BlobRole.RUN_MANIFEST not in roles:
        raise ManifestError(f"{where}.blobs: bundle must contain a run manifest")
    if BundleCapability.REPRODUCE_RUNS in capabilities:
        required_roles = {BlobRole.SOURCE, BlobRole.DEPENDENCY, BlobRole.LOCKFILE, BlobRole.ENVIRONMENT}
        missing = sorted(role.value for role in required_roles - roles)
        if missing:
            raise ManifestError(f"{where}.blobs: reproduction capability missing roles {missing}")
    return EvidenceBundle(raw["id"], capabilities, runs, tuple(blobs), limitations)


def verify_bundle(bundle: EvidenceBundle, store) -> tuple[BlobVerification, ...]:
    checks = []
    for blob in bundle.blobs:
        path = blob_path(store, blob.content.sha256)
        if not path.is_file():
            checks.append(BlobVerification(blob, BlobStatus.MISSING, None))
            continue
        actual = content_identity(path)
        status = BlobStatus.VERIFIED if actual == blob.content else BlobStatus.IDENTITY_MISMATCH
        checks.append(BlobVerification(blob, status, actual))
    return tuple(checks)
