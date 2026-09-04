"""Print the canonical per-axis Fellegi-Sunter EM diagnostic."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from decluster.experiments.em_m import build_artifact, render_markdown


if __name__ == "__main__":
    snapshot = Path(__file__).resolve().parents[1] / "data" / "fs-blkcache-2026-09-04.tar.gz"
    print(render_markdown(build_artifact(snapshot)), end="")
