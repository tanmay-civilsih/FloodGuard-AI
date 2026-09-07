import shutil
import subprocess
from pathlib import Path

from floodguard.history.preview import render_preview


def test_rainfall_preview_behavior(tmp_path):
    node = shutil.which("node")
    assert node, "Node.js is required for rainfall preview behavior tests"
    page = tmp_path / "history.html"
    page.write_text(render_preview(), encoding="utf-8")
    result = subprocess.run(
        [node, str(Path(__file__).with_name("history_preview_harness.cjs")), str(page)],
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
