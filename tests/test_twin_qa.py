import shutil
import subprocess
from pathlib import Path

from floodguard.twin.qa_viewer import QA_VIEWER_HTML


def test_twin_qa_script(tmp_path: Path) -> None:
    node = shutil.which("node")
    assert node, "Node.js is required for twin QA behavior tests"
    html = tmp_path / "twin.html"
    html.write_text(QA_VIEWER_HTML, encoding="utf-8")
    result = subprocess.run(
        [node, str(Path(__file__).with_name("twin_qa_harness.cjs")), str(html)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
