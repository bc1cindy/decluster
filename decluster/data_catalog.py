"""Offline dataset catalog operations used by tests, automation and future UIs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from urllib.request import urlopen

from .data_manifest import ContentIdentity, DatasetManifest, ManifestError, load_dataset_manifest
from .result_artifacts import content_identity
from .evidence_bundle import blob_path


class DatasetStatus(str, Enum):
    VERIFIED = "verified"
    MISSING = "missing"
    IDENTITY_MISMATCH = "identity_mismatch"


class FetchStatus(str, Enum):
    ALREADY_AVAILABLE = "already_available"
    DOWNLOADED = "downloaded"


class FetchAttemptStatus(str, Enum):
    TRANSPORT_ERROR = "transport_error"
    IDENTITY_MISMATCH = "identity_mismatch"


class PrepareStatus(str, Enum):
    ALREADY_PREPARED = "already_prepared"
    MATERIALIZED = "materialized"


class PrepareFailure(str, Enum):
    STORE_MISSING = "store_missing"
    STORE_IDENTITY_MISMATCH = "store_identity_mismatch"
    DESTINATION_IDENTITY_MISMATCH = "destination_identity_mismatch"


@dataclass(frozen=True)
class DatasetCheck:
    dataset: DatasetManifest
    status: DatasetStatus
    expected: ContentIdentity
    actual: ContentIdentity | None


@dataclass(frozen=True)
class FetchAttempt:
    url: str
    status: FetchAttemptStatus


@dataclass(frozen=True)
class FetchResult:
    dataset: DatasetManifest
    status: FetchStatus
    path: Path
    source_url: str | None


@dataclass(frozen=True)
class PrepareResult:
    dataset: DatasetManifest
    status: PrepareStatus
    path: Path


class DatasetPrepareError(RuntimeError):
    def __init__(self, dataset_id: str, failure: PrepareFailure, path: Path):
        self.dataset_id = dataset_id
        self.failure = failure
        self.path = path
        super().__init__(f"{dataset_id}: {failure.value}: {path}")


class DatasetFetchError(RuntimeError):
    def __init__(self, dataset_id: str, attempts: tuple[FetchAttempt, ...]):
        self.dataset_id = dataset_id
        self.attempts = attempts
        detail = ", ".join(f"{attempt.url}={attempt.status.value}" for attempt in attempts)
        super().__init__(f"{dataset_id}: no verified source available: {detail or 'no locations'}")


def load_dataset_catalog(root) -> tuple[DatasetManifest, ...]:
    """Load the complete catalog deterministically and reject duplicate IDs."""
    root = Path(root)
    paths = sorted((root / "catalog" / "datasets").glob("*.json"))
    if not paths:
        raise ManifestError(f"{root}: dataset catalog is empty")
    manifests = tuple(load_dataset_manifest(path) for path in paths)
    seen = set()
    for manifest in manifests:
        if manifest.id in seen:
            raise ManifestError(f"duplicate dataset id: {manifest.id!r}")
        seen.add(manifest.id)
    return manifests


def dataset_path(dataset: DatasetManifest, root) -> Path:
    """Resolve a catalog path while keeping it inside the project root."""
    root = Path(root).resolve()
    path = (root / dataset.local_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ManifestError(
            f"{dataset.id}.locations.local_path: escapes project root"
        ) from exc
    return path


def dataset_status(dataset: DatasetManifest, root) -> DatasetCheck:
    expected = dataset.content
    path = dataset_path(dataset, root)
    if not path.is_file():
        return DatasetCheck(dataset, DatasetStatus.MISSING, expected, None)
    actual = content_identity(path)
    status = DatasetStatus.VERIFIED if actual == expected else DatasetStatus.IDENTITY_MISMATCH
    return DatasetCheck(dataset, status, expected, actual)


def catalog_status(root) -> tuple[DatasetCheck, ...]:
    return tuple(dataset_status(dataset, root) for dataset in load_dataset_catalog(root))


def require_verified_datasets(root) -> tuple[DatasetManifest, ...]:
    """Return verified datasets or fail without accepting a partial catalog."""
    checks = catalog_status(root)
    failures = [check for check in checks if check.status is not DatasetStatus.VERIFIED]
    if failures:
        detail = ", ".join(f"{check.dataset.id}={check.status.value}" for check in failures)
        raise ManifestError(f"dataset catalog is not fully verified: {detail}")
    return tuple(check.dataset for check in checks)


def _download_candidate(dataset, url, directory, opener):
    digest = hashlib.sha256()
    size = 0
    with tempfile.NamedTemporaryFile(dir=directory, delete=False) as temporary:
        temporary_path = Path(temporary.name)
        try:
            with opener(url) as response:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > dataset.content.bytes:
                        return temporary_path, ContentIdentity(size, digest.hexdigest())
                    digest.update(chunk)
                    temporary.write(chunk)
            temporary.flush()
            os.fsync(temporary.fileno())
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise
    return temporary_path, ContentIdentity(size, digest.hexdigest())


def fetch_dataset(dataset: DatasetManifest, store, *, opener=urlopen) -> FetchResult:
    """Fetch one dataset into the content store, accepting only its declared bytes."""
    destination = blob_path(store, dataset.content.sha256)
    if destination.is_file() and content_identity(destination) == dataset.content:
        return FetchResult(dataset, FetchStatus.ALREADY_AVAILABLE, destination, None)

    destination.parent.mkdir(parents=True, exist_ok=True)
    attempts = []
    urls = tuple(url for url in (dataset.canonical_location, *dataset.mirrors) if url)
    for url in urls:
        try:
            temporary_path, actual = _download_candidate(dataset, url, destination.parent, opener)
        except (OSError, ValueError):
            attempts.append(FetchAttempt(url, FetchAttemptStatus.TRANSPORT_ERROR))
            continue
        try:
            if actual != dataset.content:
                attempts.append(FetchAttempt(url, FetchAttemptStatus.IDENTITY_MISMATCH))
                continue
            os.replace(temporary_path, destination)
            return FetchResult(dataset, FetchStatus.DOWNLOADED, destination, url)
        finally:
            temporary_path.unlink(missing_ok=True)
    raise DatasetFetchError(dataset.id, tuple(attempts))


def prepare_dataset(dataset: DatasetManifest, root, store, *, replace=False) -> PrepareResult:
    """Materialize one verified store blob at its declared local path."""
    destination = dataset_path(dataset, root)
    if destination.is_file():
        if content_identity(destination) == dataset.content:
            return PrepareResult(dataset, PrepareStatus.ALREADY_PREPARED, destination)
        if not replace:
            raise DatasetPrepareError(
                dataset.id, PrepareFailure.DESTINATION_IDENTITY_MISMATCH, destination,
            )
    elif destination.exists():
        raise DatasetPrepareError(
            dataset.id, PrepareFailure.DESTINATION_IDENTITY_MISMATCH, destination,
        )

    source = blob_path(store, dataset.content.sha256)
    if not source.is_file():
        raise DatasetPrepareError(dataset.id, PrepareFailure.STORE_MISSING, source)
    if content_identity(source) != dataset.content:
        raise DatasetPrepareError(
            dataset.id, PrepareFailure.STORE_IDENTITY_MISMATCH, source,
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
        with source.open("rb") as stream:
            shutil.copyfileobj(stream, temporary)
        temporary.flush()
        os.fsync(temporary.fileno())
    try:
        if content_identity(temporary_path) != dataset.content:
            raise DatasetPrepareError(
                dataset.id, PrepareFailure.STORE_IDENTITY_MISMATCH, source,
            )
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    return PrepareResult(dataset, PrepareStatus.MATERIALIZED, destination)
