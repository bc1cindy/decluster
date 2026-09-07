"""A declared canonical URL has to serve the bytes the bundle pins, or it is worse than none.

One did not. `slice_a_channels_2016.ndjson.gz` named revision `43d3faaa`, which is not on the
published branch and, after the trailer rewrite, is not on this branch either — a link that 404s
for every reader, sitting in the field that is supposed to make the bundle fetchable.

The check is content-addressed: the file at the named revision must hash to the pinned digest, and
the revision must be an ancestor of what is published. A URL that merely looks plausible fails.
"""
import json
import subprocess
from pathlib import Path

import pytest

from decluster import blob_locations

ROOT = Path(__file__).resolve().parents[1]
PUBLISHED = "origin/master"


def _has_published_branch():
    return subprocess.run(["git", "rev-parse", "--verify", PUBLISHED],
                          cwd=ROOT, capture_output=True).returncode == 0


requires_published = pytest.mark.skipif(
    not _has_published_branch(),
    reason=f"no {PUBLISHED} to resolve against; declared locations went unchecked",
)


@requires_published
def test_no_declared_location_is_dangling():
    dangling = [row for row in blob_locations.audit(ROOT, PUBLISHED) if row["state"] == "dangling"]
    assert not dangling, (
        "these name a revision that does not serve the pinned bytes:\n  "
        + "\n  ".join(f"{row['bundle']}  {row['name']}" for row in dangling)
        + "\nRun `python -m decluster.blob_locations` to clear or repoint them."
    )


@requires_published
def test_a_blob_the_published_branch_serves_is_declared():
    """Leaving one undeclared is a bundle that bootstraps from the checkout for no reason."""
    available = [row for row in blob_locations.audit(ROOT, PUBLISHED) if row["state"] == "available"]
    assert not available, f"could be declared and are not: {[r['name'] for r in available]}"


@requires_published
def test_the_declared_share_is_reported():
    """Most blobs are absent because the branch is not pushed; that is a state, not a decision."""
    rows = blob_locations.audit(ROOT, PUBLISHED)
    resolves = sum(1 for row in rows if row["state"] == "resolves")
    assert resolves >= 10, f"{resolves} of {len(rows)} resolve; this used to be 10"


def test_a_url_whose_bytes_differ_is_not_resolvable(tmp_path):
    blob = {"name": "README.md", "sha256": "0" * 64}
    assert not blob_locations.resolvable(blob, "HEAD", "HEAD", root=str(ROOT))
