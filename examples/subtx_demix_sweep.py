"""Sweep the coinjoin de-mix over the labelled fixtures:
how many participants it recovers per tx. Real Wasabi 2 coinjoins are dense/amount-private (recover 0).
Reads fixture amounts from the sibling dense-subset-sum repo as labelled DATA only (set DSS_REPO)."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decluster.coinjoin_demix import coinjoin_demix

DSS_REPO = os.environ.get("DSS_REPO", os.path.expanduser("~/dense-subset-sum"))
FIXTURE_FILES = ["src/fixtures/sets.rs", "src/fixtures/wasabi2_positive.rs", "src/fixtures/wasabi2_false.rs"]


def parse_fixtures(repo):
    """{fn_name: (inputs, outputs)} from the Rust fixture files (each `pub fn ...() -> Transaction`
    has two `vec![...]` blocks: inputs then outputs)."""
    fx = {}
    for rel in FIXTURE_FILES:
        path = os.path.join(repo, rel)
        if not os.path.exists(path):
            continue
        src = open(path).read()
        for m in re.finditer(r"pub fn (\w+)\(\)\s*->\s*Transaction\s*\{", src):
            body = src[m.end():]
            body = body[:body.find("pub fn ")] if "pub fn " in body else body
            vecs = re.findall(r"vec!\[([^\]]*)\]", body, re.S)
            if len(vecs) < 2:
                continue
            def nums(s):
                return [int(x) for x in re.findall(r"\d[\d_]*", s.replace("_", ""))]
            ins, outs = nums(vecs[0]), nums(vecs[1])
            if ins and outs:
                fx[m.group(1)] = (ins, outs)
    return fx


def recovered(ins, outs):
    return len(coinjoin_demix(ins, outs))


def run():
    fx = parse_fixtures(DSS_REPO)
    if not fx:
        print(f"no fixtures found under {DSS_REPO} (set DSS_REPO)"); return
    print(f"# {len(fx)} fixtures from {DSS_REPO} (labelled data only)\n")
    print(f"{'fixture':40} {'in':>4} {'out':>4}  {'participants':>12}")
    for name in sorted(fx):
        ins, outs = fx[name]
        print(f"{name[:40]:40} {len(ins):>4} {len(outs):>4}  {recovered(ins, outs):>12}")


if __name__ == "__main__":
    run()
