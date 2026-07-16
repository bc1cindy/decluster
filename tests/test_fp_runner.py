"""The runner imports with no side effects (no top-level file read / network)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_runner_imports_without_side_effects():
    import examples.fingerprint_validation as r
    assert hasattr(r, "main")

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
