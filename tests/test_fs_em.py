"""EM per-axis m: fs_score dict extension + fs_em engine (agree_matrix / em_fit / oracle_m)."""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _one_axis(collision=0.5):
    # a single synthetic axis: value = tx["k"]; p={"a":0.5}; never abstains
    fn = lambda tx: tx["k"]
    return [("ax", fn, {"a": 0.5}, collision, lambda va, vb: False)]


def test_fs_score_scalar_path_byte_identical():
    from decluster.combiner import fs_score
    axes = _one_axis(collision=0.5)
    agree = fs_score(axes, {"k": "a"}, {"k": "a"}, 0.95, 1000)
    disagree = fs_score(axes, {"k": "a"}, {"k": "b"}, 0.95, 1000)
    assert agree == -math.log2(0.5)                        # +1.0 bit
    assert disagree == min(0.0, math.log2((1 - 0.95) / (1 - 0.5)))


def test_fs_score_dict_applies_per_axis_c():
    from decluster.combiner import fs_score
    axes = _one_axis(collision=0.5)
    # c as dict: m=0.5 makes the disagreement weight log2((1-0.5)/(1-0.5)) = 0
    w = fs_score(axes, {"k": "a"}, {"k": "b"}, {"ax": 0.5}, 1000)
    assert w == 0.0
    # and c dict with 0.95 matches the scalar path exactly
    w95 = fs_score(axes, {"k": "a"}, {"k": "b"}, {"ax": 0.95}, 1000)
    assert w95 == fs_score(axes, {"k": "a"}, {"k": "b"}, 0.95, 1000)


def _synth(n, m_true, u_true, lam, seed):
    """Generate n pairs from a known 2-class model; all axes active. Returns (A, mask, labels)."""
    rng = random.Random(seed)
    k = len(m_true)
    A, mask, labels = [], [], []
    for _ in range(n):
        match = rng.random() < lam
        labels.append(1 if match else 0)
        probs = m_true if match else u_true
        A.append([1 if rng.random() < probs[j] else 0 for j in range(k)])
        mask.append([True] * k)
    return A, mask, labels


def test_em_recovers_known_m():
    from decluster.fs_em import em_fit
    m_true, u_true, lam = [0.95, 0.80, 0.60], [0.30, 0.20, 0.50], 0.5
    A, mask, _ = _synth(4000, m_true, u_true, lam, seed=1)
    out = em_fit(A, mask, u_true)
    for got, want in zip(out["m"], m_true):
        assert abs(got - want) < 0.05


def test_em_loglik_monotone_and_converges():
    from decluster.fs_em import em_fit
    A, mask, _ = _synth(2000, [0.9, 0.7], [0.3, 0.4], 0.5, seed=2)
    out = em_fit(A, mask, [0.3, 0.4])
    ll = out["loglik"]
    assert all(ll[i + 1] >= ll[i] - 1e-9 for i in range(len(ll) - 1))
    assert out["n_iter"] <= 100


def test_em_does_not_mutate_u():
    from decluster.fs_em import em_fit
    A, mask, _ = _synth(500, [0.9], [0.3], 0.5, seed=3)
    u = [0.3]; u_copy = list(u)
    em_fit(A, mask, u)
    assert u == u_copy


def test_em_all_abstain_pairs_get_prior():
    from decluster.fs_em import em_fit
    # 100 pairs, single axis, every pair abstains -> no evidence -> r == lam (0.5), m stays init
    A = [[0] for _ in range(100)]
    mask = [[False] for _ in range(100)]
    out = em_fit(A, mask, [0.3])
    assert all(abs(ri - 0.5) < 1e-9 for ri in out["r"])
    assert abs(out["m"][0] - 0.9) < 1e-9


def test_em_clamps_m_below_one():
    from decluster.fs_em import em_fit
    # an axis where matches always agree: m would be 1.0 -> must clamp to < 1
    A, mask, _ = _synth(1000, [0.999999], [0.2], 0.6, seed=4)
    out = em_fit(A, mask, [0.2])
    assert out["m"][0] < 1.0


def test_oracle_m_exact():
    from decluster.fs_em import oracle_m
    # 2 positives (labels=1), axis agrees on 1 of them; 1 negative ignored
    A = [[1], [0], [1]]
    mask = [[True], [True], [True]]
    labels = [1, 1, 0]
    assert oracle_m(A, mask, labels) == [0.5]


def test_oracle_m_none_when_no_active_positive():
    from decluster.fs_em import oracle_m
    A = [[1]]; mask = [[False]]; labels = [1]
    assert oracle_m(A, mask, labels) == [None]


def test_agree_matrix_shapes_and_abstain():
    from decluster.fs_em import agree_matrix
    # axis A never abstains (value = tx["k"]); axis B abstains when either value == "x"
    axes = [
        ("a", lambda tx: tx["k"], {}, 0.4, lambda va, vb: False),
        ("b", lambda tx: tx["j"], {}, 0.6, lambda va, vb: "x" in (va, vb)),
    ]
    pairs = [({"k": "p", "j": "x"}, {"k": "p", "j": "y"})]     # A agrees; B abstains
    A, mask, names, u = agree_matrix(pairs, axes)
    assert names == ["a", "b"] and u == [0.4, 0.6]
    assert A[0] == [1, 0] and mask[0] == [True, False]
