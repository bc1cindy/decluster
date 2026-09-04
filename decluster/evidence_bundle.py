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
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.request import urlopen

from .data_manifest import ContentIdentity, ManifestError, SHA256
from .data_manifest import Redistribution, load_run_manifest
from .reference_registry import load_claims, load_sources
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


class AcquisitionStatus(str, Enum):
    ALREADY_AVAILABLE = "already_available"
    DOWNLOADED = "downloaded"


class MaterializationStatus(str, Enum):
    ALREADY_MATERIALIZED = "already_materialized"
    MATERIALIZED = "materialized"


class ReproductionStatus(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"


class ReadinessIssueKind(str, Enum):
    CAPABILITY_MISSING = "capability_missing"
    BLOB_MISSING = "blob_missing"
    BLOB_IDENTITY_MISMATCH = "blob_identity_mismatch"
    REQUIRED_ROLE_MISSING = "required_role_missing"
    CANONICAL_LOCATION_MISSING = "canonical_location_missing"
    MIRROR_MISSING = "mirror_missing"
    RUN_MANIFEST_MISSING = "run_manifest_missing"
    DEPENDENCY_EDITABLE = "dependency_editable"
    DEPENDENCY_LICENSE_UNKNOWN = "dependency_license_unknown"
    DEPENDENCY_REDISTRIBUTION_NOT_ALLOWED = "dependency_redistribution_not_allowed"
    DEPENDENCY_LOCK_MISSING = "dependency_lock_missing"
    ENVIRONMENT_LOCK_MISSING = "environment_lock_missing"


@dataclass(frozen=True)
class BundleBlob:
    name: str
    role: BlobRole
    content: ContentIdentity
    canonical_location: str | None
    mirrors: tuple[str, ...]


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


@dataclass(frozen=True)
class BootstrapResult:
    blob: BundleBlob
    acquisition: AcquisitionStatus
    materialization: MaterializationStatus
    path: Path
    source_url: str | None


@dataclass(frozen=True)
class ReadinessIssue:
    kind: ReadinessIssueKind
    subject: str
    detail: str


@dataclass(frozen=True)
class ReproductionReadiness:
    status: ReproductionStatus
    issues: tuple[ReadinessIssue, ...]


class BundleBootstrapError(RuntimeError):
    pass


class BundleReproductionError(RuntimeError):
    pass


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


def _safe_target(root, name):
    root = Path(root).resolve()
    target = (root / name).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ManifestError(f"bundle blob name escapes target root: {name!r}") from exc
    return target


def _https(value, where, *, nullable=False):
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value.startswith("https://"):
        raise ManifestError(f"{where}: expected https URL")
    return value


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
        expected_keys = {"name", "role", "bytes", "sha256", "locations"}
        if not isinstance(item, dict) or set(item) != expected_keys:
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
        locations = item["locations"]
        if not isinstance(locations, dict) or set(locations) != {"canonical", "mirrors"}:
            raise ManifestError(f"{item_where}.locations: invalid locations")
        canonical = _https(locations["canonical"], f"{item_where}.locations.canonical", nullable=True)
        mirrors = locations["mirrors"]
        if not isinstance(mirrors, list) or len(mirrors) != len(set(mirrors)):
            raise ManifestError(f"{item_where}.locations.mirrors: expected unique array")
        mirrors = tuple(
            _https(url, f"{item_where}.locations.mirrors[{position}]")
            for position, url in enumerate(mirrors)
        )
        _safe_target(Path.cwd(), name)
        blobs.append(BundleBlob(name, role, ContentIdentity(size, digest), canonical, mirrors))
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


def assess_reproduction_readiness(bundle: EvidenceBundle, store, root) -> ReproductionReadiness:
    """Report every known obstacle to independent cold-start reproduction.

    This is deliberately stricter than bundle verification. A ready bundle must
    be downloadable from a canonical location and a mirror, contain the full
    execution environment, and avoid mutable or legally ambiguous dependencies.
    """
    from .data_catalog import load_dataset_catalog

    root = Path(root)
    issues = []

    def add(kind, subject, detail):
        issues.append(ReadinessIssue(kind, subject, detail))

    if BundleCapability.REPRODUCE_RUNS not in bundle.capabilities:
        add(ReadinessIssueKind.CAPABILITY_MISSING, bundle.id, "reproduce_runs")

    checks = verify_bundle(bundle, store)
    checks_by_name = {check.blob.name: check for check in checks}
    for check in checks:
        if check.status is BlobStatus.MISSING:
            add(ReadinessIssueKind.BLOB_MISSING, check.blob.name, "content-addressed blob")
        elif check.status is BlobStatus.IDENTITY_MISMATCH:
            add(ReadinessIssueKind.BLOB_IDENTITY_MISMATCH, check.blob.name, "SHA-256 or size")

    roles = {blob.role for blob in bundle.blobs}
    for role in sorted(
        {BlobRole.SOURCE, BlobRole.DEPENDENCY, BlobRole.LOCKFILE, BlobRole.ENVIRONMENT} - roles,
        key=lambda item: item.value,
    ):
        add(ReadinessIssueKind.REQUIRED_ROLE_MISSING, role.value, "bundle blob role")

    for blob in bundle.blobs:
        if blob.canonical_location is None:
            add(ReadinessIssueKind.CANONICAL_LOCATION_MISSING, blob.name, "public HTTPS location")
        if not blob.mirrors:
            add(ReadinessIssueKind.MIRROR_MISSING, blob.name, "independent HTTPS mirror")

    sources = load_sources(root / "catalog" / "ctp-sources.json")
    claims = load_claims(root / "catalog" / "ctp-claims.json", {source.id for source in sources})
    datasets = {dataset.id: dataset for dataset in load_dataset_catalog(root)}
    run_blobs = {blob.name: blob for blob in bundle.blobs if blob.role is BlobRole.RUN_MANIFEST}
    for run_id in bundle.runs:
        name = f"catalog/runs/{run_id}.json"
        if name not in run_blobs:
            add(ReadinessIssueKind.RUN_MANIFEST_MISSING, run_id, name)
            continue
        if checks_by_name[name].status is not BlobStatus.VERIFIED:
            continue
        run = load_run_manifest(
            blob_path(store, run_blobs[name].content.sha256),
            claim_ids={claim.id for claim in claims},
            datasets=datasets,
        )
        if run.lock_digest is None:
            add(ReadinessIssueKind.ENVIRONMENT_LOCK_MISSING, run.id, "environment.lock_digest")
        for dependency in run.dependencies:
            subject = f"{run.id}:{dependency.name}"
            if dependency.editable:
                add(ReadinessIssueKind.DEPENDENCY_EDITABLE, subject, dependency.source)
            if dependency.license.strip().lower() in {"unknown", "none", "unlicensed"}:
                add(ReadinessIssueKind.DEPENDENCY_LICENSE_UNKNOWN, subject, dependency.license)
            if dependency.redistribution is not Redistribution.ALLOWED:
                add(
                    ReadinessIssueKind.DEPENDENCY_REDISTRIBUTION_NOT_ALLOWED,
                    subject,
                    dependency.redistribution.value,
                )
            if dependency.lock_sha256 is None:
                add(ReadinessIssueKind.DEPENDENCY_LOCK_MISSING, subject, "dependency lock SHA-256")

    status = ReproductionStatus.READY if not issues else ReproductionStatus.BLOCKED
    return ReproductionReadiness(status, tuple(issues))


def _fetch_blob(blob, store, opener):
    destination = blob_path(store, blob.content.sha256)
    if destination.is_file() and content_identity(destination) == blob.content:
        return AcquisitionStatus.ALREADY_AVAILABLE, destination, None
    destination.parent.mkdir(parents=True, exist_ok=True)
    failures = []
    for url in tuple(x for x in (blob.canonical_location, *blob.mirrors) if x):
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            size = 0
            try:
                with opener(url) as response:
                    while chunk := response.read(1024 * 1024):
                        size += len(chunk)
                        if size > blob.content.bytes:
                            break
                        temporary.write(chunk)
                temporary.flush()
                os.fsync(temporary.fileno())
            except (OSError, ValueError):
                failures.append(f"{url}=transport_error")
                temporary_path.unlink(missing_ok=True)
                continue
        try:
            if size != blob.content.bytes or content_identity(temporary_path) != blob.content:
                failures.append(f"{url}=identity_mismatch")
                continue
            os.replace(temporary_path, destination)
            return AcquisitionStatus.DOWNLOADED, destination, url
        finally:
            temporary_path.unlink(missing_ok=True)
    raise BundleBootstrapError(
        f"{blob.name}: no verified source available: {', '.join(failures) or 'no locations'}"
    )


def _materialize_blob(blob, source, root, *, replace):
    target = _safe_target(root, blob.name)
    if target.is_file():
        if content_identity(target) == blob.content:
            return MaterializationStatus.ALREADY_MATERIALIZED, target
        if not replace:
            raise BundleBootstrapError(f"{blob.name}: destination_identity_mismatch: {target}")
    elif target.exists():
        raise BundleBootstrapError(f"{blob.name}: destination_identity_mismatch: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
        with source.open("rb") as stream:
            shutil.copyfileobj(stream, temporary)
        temporary.flush()
        os.fsync(temporary.fileno())
    try:
        if content_identity(temporary_path) != blob.content:
            raise BundleBootstrapError(f"{blob.name}: store_identity_mismatch: {source}")
        os.replace(temporary_path, target)
    finally:
        temporary_path.unlink(missing_ok=True)
    return MaterializationStatus.MATERIALIZED, target


def bootstrap_bundle(bundle: EvidenceBundle, store, root, *, opener=urlopen, replace=False):
    """Acquire and materialize blobs in index order, raising on the first failure."""
    results = []
    for blob in bundle.blobs:
        acquisition, source, source_url = _fetch_blob(blob, store, opener)
        materialization, target = _materialize_blob(blob, source, root, replace=replace)
        results.append(BootstrapResult(blob, acquisition, materialization, target, source_url))
    return tuple(results)


def _load_environment(path):
    where = str(path)
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BundleReproductionError(f"{where}: cannot read environment: {exc}") from exc
    required = {
        "schema_version", "python", "source_archive", "project_root", "requirements",
        "dependency_directory",
    }
    if not isinstance(raw, dict) or set(raw) != required or raw["schema_version"] != 1:
        raise BundleReproductionError(f"{where}: invalid reproduction environment")
    python = raw["python"]
    if not isinstance(python, dict) or set(python) != {
        "implementation", "version", "system", "machine",
    }:
        raise BundleReproductionError(f"{where}.python: invalid interpreter contract")
    for field in ("implementation", "version", "system", "machine"):
        if not isinstance(python[field], str) or not python[field]:
            raise BundleReproductionError(f"{where}.python.{field}: expected non-empty string")
    for field in ("source_archive", "project_root", "requirements", "dependency_directory"):
        if not isinstance(raw[field], str) or not raw[field]:
            raise BundleReproductionError(f"{where}.{field}: expected non-empty string")
    return raw


def _require_compatible_interpreter(contract):
    actual = {
        "implementation": platform.python_implementation().lower(),
        "version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "system": platform.system(),
        "machine": platform.machine(),
    }
    if actual != contract:
        raise BundleReproductionError(
            f"incompatible interpreter: expected {contract!r}, found {actual!r}"
        )


def _extract_source(archive, destination):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive, mode="r:") as source:
        for member in source.getmembers():
            if not (member.isfile() or member.isdir()):
                raise BundleReproductionError(
                    f"source archive contains unsupported entry: {member.name!r}"
                )
            _safe_target(destination, member.name)
        extraction_options = {"filter": "fully_trusted"} if sys.version_info >= (3, 12) else {}
        source.extractall(destination, **extraction_options)


def _run_checked(argv, *, cwd, env=None):
    try:
        subprocess.run(argv, cwd=cwd, env=env, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise BundleReproductionError(f"command failed: {argv!r}") from exc


def reproduce_bundle(bundle: EvidenceBundle, root, work, *, interpreter=sys.executable):
    """Reexecute every declared run using only materialized bundle contents.

    Network access is disabled at the package-manager layer. Callers performing a cold-start audit
    should additionally isolate the process from the network at the operating-system level.
    """
    if BundleCapability.REPRODUCE_RUNS not in bundle.capabilities:
        raise BundleReproductionError(f"{bundle.id}: reproduce_runs capability is not declared")
    root = Path(root).resolve()
    environments = [blob for blob in bundle.blobs if blob.role is BlobRole.ENVIRONMENT]
    if len(environments) != 1:
        raise BundleReproductionError(f"{bundle.id}: expected exactly one environment blob")
    specification = _load_environment(_safe_target(root, environments[0].name))
    _require_compatible_interpreter(specification["python"])

    work = Path(work).resolve()
    if work.exists():
        raise BundleReproductionError(f"work directory already exists: {work}")
    work.mkdir(parents=True)
    source_root = work / "source"
    _extract_source(_safe_target(root, specification["source_archive"]), source_root)
    checkout = _safe_target(source_root, specification["project_root"])
    if not checkout.is_dir():
        raise BundleReproductionError(f"project root is missing from source archive: {checkout}")

    virtualenv = work / "venv"
    _run_checked([interpreter, "-m", "venv", str(virtualenv)], cwd=work)
    python = virtualenv / "bin" / "python"
    if not python.is_file():
        raise BundleReproductionError("the declared environment requires a POSIX Python layout")
    requirements = _safe_target(root, specification["requirements"])
    dependencies = _safe_target(root, specification["dependency_directory"])
    _run_checked([
        str(python), "-m", "pip", "install", "--no-index", "--no-cache-dir",
        "--disable-pip-version-check", "--require-hashes",
        "--find-links", str(dependencies), "--requirement", str(requirements),
    ], cwd=work)

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(checkout)
    sources = load_sources(checkout / "catalog" / "ctp-sources.json")
    claims = load_claims(
        checkout / "catalog" / "ctp-claims.json", {source.id for source in sources}
    )
    from .data_catalog import load_dataset_catalog
    datasets = {dataset.id: dataset for dataset in load_dataset_catalog(checkout)}
    outputs = []
    for run_id in bundle.runs:
        manifest = load_run_manifest(
            _safe_target(root, f"catalog/runs/{run_id}.json"),
            claim_ids={claim.id for claim in claims},
            datasets=datasets,
        )
        argv = [str(python), *manifest.argv[1:]]
        _run_checked(argv, cwd=checkout, env=environment)
        _run_checked([str(python), *manifest.verification.argv[1:]], cwd=checkout, env=environment)
        for output in manifest.outputs:
            path = _safe_target(checkout, output.path)
            actual = content_identity(path)
            expected = ContentIdentity(output.bytes, output.sha256)
            if actual != expected:
                raise BundleReproductionError(
                    f"{run_id}: reproduced output identity mismatch: {output.path}"
                )
            outputs.append(path)
    return tuple(outputs)
