import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_uf_preseeded_singletons_appear():
    from decluster.unionfind import UF
    uf = UF(["a", "b", "c"])          # pre-seeded
    uf.union("a", "b")
    groups = sorted(sorted(g) for g in uf.groups())
    assert groups == [["a", "b"], ["c"]]      # untouched "c" still a singleton group

def test_uf_lazy_adds_unknown():
    from decluster.unionfind import UF
    uf = UF()                          # lazy
    uf.union("x", "y")
    assert uf.find("x") == uf.find("y")
    assert sorted(uf.group("x")) == ["x", "y"]

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
