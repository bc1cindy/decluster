import subprocess
import sys

import decluster


def test_public_api_names_are_importable_and_callable():
    for name in (
        "analyze",
        "cluster_map",
        "cluster_posterior",
        "bounded_link_oracle",
        "subprocess_link_oracle",
    ):
        assert hasattr(decluster, name)
        assert callable(getattr(decluster, name))


def test_importing_decluster_does_not_load_dss():
    result = subprocess.run(
        [sys.executable, "-c", "import sys, decluster; assert 'dss' not in sys.modules"]
    )
    assert result.returncode == 0
