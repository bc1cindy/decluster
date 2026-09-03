from decluster import reproducibility as rp


def test_fingerprint_counts_files_and_bytes(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"x" * 10)
    (tmp_path / "b.txt").write_bytes(b"y" * 20)
    fp = rp.fingerprint_source(str(tmp_path / "*.txt"))
    assert fp["files"] == 2
    assert fp["bytes"] == 30
    assert len(fp["digest"]) == 64


def test_fingerprint_digest_changes_when_a_file_grows(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"x" * 10)
    before = rp.fingerprint_source(str(tmp_path / "*.txt"))["digest"]
    (tmp_path / "a.txt").write_bytes(b"x" * 11)
    assert rp.fingerprint_source(str(tmp_path / "*.txt"))["digest"] != before


def test_fingerprint_digest_changes_on_a_rename_at_equal_size(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"x" * 10)
    before = rp.fingerprint_source(str(tmp_path / "*.txt"))["digest"]
    (tmp_path / "a.txt").rename(tmp_path / "b.txt")
    assert rp.fingerprint_source(str(tmp_path / "*.txt"))["digest"] != before


def test_fingerprint_reports_missing_rather_than_raising(tmp_path):
    fp = rp.fingerprint_source(str(tmp_path / "nothing" / "*.gz"))
    assert fp["missing"] is True
    assert "files" not in fp


def _seeded(tmp_path, n=5):
    (tmp_path / "src.txt").write_bytes(b"z" * n)
    rp.write_manifest("RESULTS-demo.md", str(tmp_path / "*.txt"),
                      {"n_owners": 57}, root=str(tmp_path))


def test_manifest_round_trips(tmp_path):
    _seeded(tmp_path)
    m = rp.read_manifest("RESULTS-demo.md", root=str(tmp_path))
    assert m["invariants"]["n_owners"] == 57
    assert m["source"]["files"] == 1


def test_check_is_ok_when_invariants_are_supplied_and_match(tmp_path):
    _seeded(tmp_path)
    status, msg = rp.check_manifest("RESULTS-demo.md", {"n_owners": 57}, root=str(tmp_path))
    assert status == "ok", msg


def test_check_reports_identity_only_when_no_invariants_are_supplied(tmp_path):
    _seeded(tmp_path)
    status, msg = rp.check_manifest("RESULTS-demo.md", root=str(tmp_path))
    assert status == "identity-only"
    assert "NOT checked" in msg


def test_check_is_stale_when_the_source_changed(tmp_path):
    _seeded(tmp_path)
    (tmp_path / "src.txt").write_bytes(b"z" * 500)
    status, msg = rp.check_manifest("RESULTS-demo.md", root=str(tmp_path))
    assert status == "stale"
    assert "source moved" in msg


def test_check_is_stale_when_an_invariant_moved(tmp_path):
    _seeded(tmp_path)
    status, msg = rp.check_manifest("RESULTS-demo.md", {"n_owners": 32}, root=str(tmp_path))
    assert status == "stale"
    assert "n_owners" in msg


def test_check_reports_absent_source_distinctly(tmp_path):
    _seeded(tmp_path)
    (tmp_path / "src.txt").unlink()
    assert rp.check_manifest("RESULTS-demo.md", root=str(tmp_path))[0] == "absent"


def test_check_reports_unrecorded_for_a_doc_with_no_manifest(tmp_path):
    assert rp.check_manifest("RESULTS-nope.md", root=str(tmp_path))[0] == "unrecorded"


def test_check_manifest_verdict_does_not_depend_on_the_callers_cwd(tmp_path, monkeypatch):
    # A relative source pattern must resolve against `root`, never against os.getcwd() -- that bug
    # made the identical manifest read "stale" from one working directory and "absent" from
    # another, and the walker's "absent" skip is indistinguishable from unversioned data legitimately
    # not being there.
    (tmp_path / "src.txt").write_bytes(b"z" * 5)
    rp.write_manifest("RESULTS-demo.md", "src.txt", {"n_owners": 57}, root=str(tmp_path))

    monkeypatch.chdir(tmp_path)
    from_root = rp.check_manifest("RESULTS-demo.md", {"n_owners": 57}, root=str(tmp_path))

    elsewhere = tmp_path.parent
    assert elsewhere != tmp_path
    monkeypatch.chdir(elsewhere)
    from_elsewhere = rp.check_manifest("RESULTS-demo.md", {"n_owners": 57}, root=str(tmp_path))

    assert from_root == from_elsewhere == ("ok", from_root[1])


def test_manifest_path_strips_the_suffix_rather_than_the_substring(tmp_path):
    import os
    def base(doc):
        return os.path.basename(rp.manifest_path(doc, root=str(tmp_path)))
    assert base("RESULTS-demo.md") == "RESULTS-demo.json"
    assert base("RESULTS-demo") == "RESULTS-demo.json"
    assert base("a.mdx.md") == "a.mdx.json"
    assert base("x.md.notes.md") == "x.md.notes.json"


import pytest


def test_exact_mcnemar_matches_known_values():
    assert rp.separable(3, 0, effect=1.0, min_effect=0.0)[1] == pytest.approx(0.25)
    assert rp.separable(3, 1, effect=1.0, min_effect=0.0)[1] == pytest.approx(0.625)
    assert rp.separable(6, 0, effect=1.0, min_effect=0.0)[1] == pytest.approx(0.03125)


def test_three_against_zero_does_not_separate():
    verdict, p = rp.separable(3, 0, effect=1.0, min_effect=0.0)
    assert verdict is None and p > 0.05


def test_six_against_zero_separates():
    assert rp.separable(6, 0, effect=1.0, min_effect=0.0)[0] == "a"


def test_it_does_not_say_a_won_when_b_won():
    """The failure this whole instrument exists to prevent, in one assertion: B won the discordant
    pairs, but `effect` was passed positive (as if favoring A) -- the direction mismatch must not
    be read as an A win."""
    verdict, p = rp.separable(0, 20, effect=1.0, min_effect=0.0)
    assert p < 0.05
    assert verdict is None


def test_a_decisive_inversion_is_reported_as_b_not_as_noise():
    """A false verdict and a decisive inversion must not look alike: this is the historical failure
    (a published sign inverted with the suite green), and `separable` must name it "b", distinctly
    from the true-noise case below, even though neither is a verdict for A."""
    verdict, p = rp.separable(0, 60, effect=-1.0, min_effect=0.01)
    assert verdict == "b"
    assert p < 1e-15


def test_a_negative_effect_is_not_a_win_for_a():
    assert rp.separable(20, 0, effect=-1.0, min_effect=0.0)[0] is None


def test_a_significant_but_tiny_effect_does_not_separate():
    verdict, p = rp.separable(20, 0, effect=0.001, min_effect=0.02)
    assert p < 0.05 and verdict is None


def test_true_noise_is_not_separable_and_is_distinct_from_an_inversion():
    verdict, p = rp.separable(5, 5, effect=0.0, min_effect=0.01)
    assert verdict is None
    assert p == pytest.approx(1.0)


def test_no_discordant_pairs_is_not_separable():
    assert rp.separable(0, 0, effect=1.0, min_effect=0.0) == (None, 1.0)


def test_a_near_tie_at_scale_falls_back_and_is_fast():
    """A near-even split is the only shape the exact sum is expensive for, and it is also the shape
    that returns no verdict either way, so the approximation's error cannot change the answer."""
    import time
    start = time.time()
    verdict, _ = rp.separable(16000, 16000, effect=1.0, min_effect=0.0)
    assert time.time() - start < 1.0
    assert verdict is None


def test_a_lopsided_discordance_at_scale_stays_exact_and_is_fast():
    """The exact sum costs min(a, b) terms. The decisive shape a direction claim actually takes is
    cheap to compute exactly no matter how large the sample, so it must not reach the fallback."""
    import time
    start = time.time()
    verdict, p = rp.separable(100_000, 200, effect=1.0, min_effect=0.0)
    assert time.time() - start < 1.0
    assert verdict == "a" and p < 1e-15


@pytest.mark.parametrize("a,b", [(533, 470), (549, 485)])
def test_borderline_pairs_are_not_separated_by_the_approximation(a, b):
    """These sat just above alpha exactly and just below it under an uncorrected normal
    approximation, so the instrument reported a direction the exact test refuses."""
    verdict, p = rp.separable(a, b, effect=1.0, min_effect=0.0)
    assert p >= 0.05
    assert verdict is None
