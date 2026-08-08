"""Robust oracle layer on top of `ancestry.dss_link_oracle`: an in-process, panic-safe default
(`bounded_link_oracle`) plus an opt-in, hang-proof subprocess oracle (`subprocess_link_oracle`)
for the rare tx where dss's own `budget_ms` fails to preempt an internal blow-up."""
import multiprocessing as mp

from decluster import ancestry

# A cooperative dss budget that RESOLVES a ~2.3s payment+partial-mix coinjoin; 1500-2000ms
# truncates such a tx to a point mass -- confirmed on live data. This is the default budget for
# the public analyze() facade, distinct from ancestry.DEFAULT_LINK_BUDGET_MS (2000).
DEFAULT_ANALYZE_BUDGET_MS = 6000


def bounded_link_oracle(budget_ms=DEFAULT_ANALYZE_BUDGET_MS):
    """Build the default in-process link oracle: `(inputs, outputs) -> matrix|None`, bound to
    `budget_ms`. Panic-safe (inherits ancestry.dss_link_oracle's BaseException hardening), no
    subprocess. This is the default oracle the public `analyze()` facade uses."""
    def link(inputs, outputs):
        return ancestry.dss_link_oracle(inputs, outputs, budget_ms)
    return link


def _link_worker(inputs, outputs, budget_ms, q):
    import dss
    try:
        q.put(dss.pairwise_link_prob(inputs, outputs, budget_ms))
    except BaseException:
        # dss can hard-panic (pyo3_runtime.PanicException, a BaseException) on pathological
        # inputs, e.g. a `set.len() <= 64` assertion seen on a 27-input tx during probing; treat
        # that the same as a normal refusal.
        q.put(None)


def subprocess_link_oracle(inputs, outputs, wall_ms=1500):
    """Explicit opt-in, hang-proof link oracle: runs the dss call in a throwaway subprocess and
    kills it on a wall-clock deadline, an OS-level bound that works even when dss's own
    `budget_ms` is cooperative and fails to preempt an internal blow-up. Times out -> None
    (truncate), the same contract as `ancestry.dss_link_oracle`.

    macOS uses `spawn`: the program entry point MUST be guarded by `if __name__ == "__main__":`.
    An unguarded caller makes every spawned worker re-import (and re-run) the entry module, and
    the oracle fails closed to None."""
    q = mp.Queue()
    p = mp.Process(target=_link_worker, args=(inputs, outputs, wall_ms, q))
    p.start()
    p.join(wall_ms / 1000.0 + 0.5)
    if p.is_alive():
        p.terminate()
        p.join(0.5)
        if p.is_alive():
            p.kill()
            p.join()
        return None
    try:
        return q.get_nowait()
    except Exception:
        return None
