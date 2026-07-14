"""test rate-limit robustness of fetch helpers"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_backoff_retries_on_429(monkeypatch=None):
    import decluster.fetch as f
    import urllib.error
    calls = {"n": 0}
    class FakeResp:
        def read(self): return b'"okhash"'
    def fake_urlopen(url, timeout=0):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", None, None)
        return FakeResp()
    saved_open, saved_sleep = f.urllib.request.urlopen, f._sleep
    try:
        f.urllib.request.urlopen = fake_urlopen
        f._sleep = lambda s: None      # don't actually sleep in the test
        assert f._request("http://x") == '"okhash"'
        assert calls["n"] == 3          # failed twice (429), succeeded on the third
    finally:
        f.urllib.request.urlopen, f._sleep = saved_open, saved_sleep

def test_get_text_uses_request():
    import decluster.fetch as f
    saved = f._request
    try:
        f._request = lambda url: "  deadbeef  "
        assert f._get_text("http://x") == "deadbeef"
    finally:
        f._request = saved

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print(f"  ok  {name}")
    print("2 passed")
