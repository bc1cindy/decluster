"""The published block slice is read, never written.

Two result manifests fingerprint `.blkcache` file-for-file, so a live fetch landing there moves a
source that published numbers were measured on. It happened once with the suite green.
"""
import json

import pytest

from decluster import fetch


@pytest.fixture
def caches(tmp_path, monkeypatch):
    published, live = tmp_path / "blk", tmp_path / "blk-live"
    published.mkdir()
    live.mkdir()
    monkeypatch.setattr(fetch, "BLK", str(published))
    monkeypatch.setattr(fetch, "BLK_LIVE", str(live))
    return published, live


def test_a_published_block_is_served_without_a_request(caches, monkeypatch):
    published, live = caches
    (published / "abc_0.json").write_text(json.dumps([{"txid": "t"}]))
    monkeypatch.setattr(fetch, "_get", lambda url: pytest.fail(f"requested {url}"))
    assert fetch.fetch_block_txs("abc", 0) == [{"txid": "t"}]
    assert not list(live.iterdir())


def test_a_fetched_block_lands_beside_the_published_slice_not_in_it(caches, monkeypatch):
    published, live = caches
    monkeypatch.setattr(fetch, "_get", lambda url: [{"txid": "fresh"}])
    assert fetch.fetch_block_txs("def", 25) == [{"txid": "fresh"}]
    assert not list(published.iterdir())
    assert [path.name for path in live.iterdir()] == ["def_25.json"]


def test_a_block_already_fetched_is_not_requested_twice(caches, monkeypatch):
    _published, live = caches
    (live / "ghi_0.json").write_text(json.dumps([{"txid": "cached"}]))
    monkeypatch.setattr(fetch, "_get", lambda url: pytest.fail(f"requested {url}"))
    assert fetch.fetch_block_txs("ghi", 0) == [{"txid": "cached"}]
