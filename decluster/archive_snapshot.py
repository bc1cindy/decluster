"""Safe extraction of immutable dataset archives."""

from pathlib import Path, PurePosixPath
import tarfile


class UnsafeArchiveError(ValueError):
    """An archive contains an entry outside the supported regular-file subset."""


def extract_tar_gz(archive, destination):
    """Extract regular files and directories without links or path traversal."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, mode="r:gz") as source:
        members = source.getmembers()
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise UnsafeArchiveError(f"unsafe archive path: {member.name!r}")
            if not (member.isfile() or member.isdir()):
                raise UnsafeArchiveError(
                    f"unsupported archive entry: {member.name!r}"
                )
        source.extractall(destination, members=members, filter="data")
    return destination
