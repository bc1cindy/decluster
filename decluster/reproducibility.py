"""Provenance and separability for published results.

Two instruments, because results make two kinds of claim. A *level* (a survival curve, a rate) is
pinned by a band and by the data it was measured on; a *direction* (A beats B) is pinned by a paired
test with a pre-registered effect size. Conflating them is how a published sign inverted with the
suite green.
"""
import glob
import hashlib
import json
import math
import os

__all__ = ["fingerprint_source", "manifest_path", "write_manifest", "read_manifest", "check_manifest", "separable"]


def fingerprint_source(pattern):
    """Identity of the data behind a result: file count, total bytes, and a digest over the sorted
    (name, size) list. Never reads contents, so it is usable on multi-GB sources. A source that is
    not present returns `{"pattern": ..., "missing": True}` rather than raising: absence is the
    normal case for unversioned data and must be reportable."""
    paths = sorted(p for p in glob.glob(pattern) if os.path.isfile(p))
    if not paths:
        return {"pattern": pattern, "missing": True}
    total = 0
    h = hashlib.sha256()
    for p in paths:
        size = os.path.getsize(p)
        total += size
        h.update(os.path.basename(p).encode()); h.update(b"\0")
        h.update(str(size).encode()); h.update(b"\n")
    return {"pattern": pattern, "files": len(paths), "bytes": total, "digest": h.hexdigest()}


MANIFEST_DIR = "results/manifests"


def _root(root):
    return root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def manifest_path(doc, root=None):
    stem = doc[:-3] if doc.endswith(".md") else doc          # suffix strip, not substring removal
    return os.path.join(_root(root), MANIFEST_DIR, stem + ".json")


def _rooted_pattern(pattern, root):
    """A glob pattern resolved against `root` rather than the caller's CWD, so recording and
    checking a manifest see the same source regardless of where either runs from. An already-
    absolute pattern is left alone."""
    return pattern if os.path.isabs(pattern) else os.path.join(_root(root), pattern)


def write_manifest(doc, pattern, invariants, root=None):
    """Record what a result was measured on: the source's identity, and the population facts the
    claim depends on — the ones a byte digest cannot see. `pattern` is resolved against `root`
    (like `check_manifest`) so the identity recorded here is what a later, differently-rooted check
    will actually see; the pattern stored in the manifest stays as given, so a committed manifest
    stays portable across checkouts."""
    path = manifest_path(doc, root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    source = fingerprint_source(_rooted_pattern(pattern, root))
    source["pattern"] = pattern
    manifest = {"doc": doc, "source": source, "invariants": dict(invariants)}
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True); fh.write("\n")
    return manifest


def read_manifest(doc, root=None):
    path = manifest_path(doc, root)
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)


def check_manifest(doc, invariants=None, root=None):
    """`(status, message)` where status is one of:

      `unrecorded`     no manifest for this document
      `absent`         the source is not present; nothing was checked
      `identity-only`  the source matches, but no invariants were supplied to compare
      `stale`          the source moved, or a supplied invariant disagrees
      `ok`             source and every supplied invariant match

    `identity-only` is not a success. The failure this exists to catch was a source growing while
    its population degenerated, which a digest cannot see; answering `ok` with no invariant
    compared would report success on exactly that run.
    """
    recorded = read_manifest(doc, root)
    if recorded is None:
        return "unrecorded", f"{doc}: no manifest in {MANIFEST_DIR}"
    live = fingerprint_source(_rooted_pattern(recorded["source"]["pattern"], root))
    if live.get("missing"):
        return "absent", f"{doc}: source {live['pattern']} not present; nothing checked"
    was, now = recorded["source"], live
    if was.get("digest") != now.get("digest"):
        return "stale", (f"{doc}: source moved — was {was.get('files')} files / {was.get('bytes')} "
                         f"bytes, now {now['files']} / {now['bytes']}")
    if not invariants:
        return "identity-only", (f"{doc}: source unchanged; {len(recorded['invariants'])} recorded "
                                 f"invariant(s) NOT checked (none supplied)")
    for key, want in invariants.items():
        got = recorded["invariants"].get(key)
        if got != want:
            return "stale", f"{doc}: invariant {key} recorded {got}, measured {want}"
    return "ok", f"{doc}: source and {len(invariants)} invariant(s) unchanged"


EXACT_MAX_TAIL = 2000     # the exact sum costs min(a, b) terms, not a + b: a lopsided discordance
                          # stays exact at any sample size, and only a near-tie reaches the fallback


def _binom_cdf_half(k, n):
    return sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)


def _two_sided_p(a, b):
    n = a + b
    if n == 0:
        return 1.0
    if min(a, b) <= EXACT_MAX_TAIL:
        return min(1.0, 2.0 * _binom_cdf_half(min(a, b), n))
    # Continuity correction. Without it the approximation is anti-conservative on exactly the
    # pairs that sit against alpha, reporting a separation the exact test refuses.
    return math.erfc(max(abs(a - b) - 1.0, 0.0) / math.sqrt(n) / math.sqrt(2.0))


def separable(wins_a, wins_b, effect, min_effect, alpha=0.05):
    """Did A beat B, did B beat A, or is the difference noise?

    `wins_a` / `wins_b` are the DISCORDANT counts — cases where exactly one arm was right.
    Concordant cases carry no information about a difference; excluding them is what makes this
    the paired test rather than two independent proportions.

    Three gates, all of which must clear for either direction. **The arm must actually have won**
    on the discordant counts — a function that answers "A" when B won the discordant pairs is the
    failure this instrument exists to prevent. The p-value answers "could this be chance". `effect`
    is signed (positive favors A, negative favors B) and `min_effect` is PRE-REGISTERED, answering
    "is it large enough to matter": without it a large sample makes any difference significant and a
    small one makes every difference unmeasured. A verdict requires the win-count direction and the
    effect's sign to agree; a mismatch (e.g. B won the discordant pairs but `effect` was passed
    positive) is reported as `None`, the same as genuine noise, rather than guessed past to a
    verdict.

    Returns `(verdict, p)` where verdict is `"a"`, `"b"`, or `None` — never a bare bool, because a
    decisive inversion (B wins outright, p astronomically small) and true noise (p ≈ 1) are both
    "not a verdict for A" but are not the same finding, and the historical failure this instrument
    exists to name was the former, not the latter. `None` is state 5: measured, not separable.

    One-sided in effect: this compares a two-sided p-value against `alpha` while also gating on
    which arm won, which is a one-sided test at `alpha/2` — conservative and defensible, but worth
    stating rather than leaving implicit.
    """
    p = _two_sided_p(wins_a, wins_b)
    significant = p < alpha
    if wins_a > wins_b and effect >= min_effect and significant:
        return "a", p
    if wins_b > wins_a and -effect >= min_effect and significant:
        return "b", p
    return None, p
