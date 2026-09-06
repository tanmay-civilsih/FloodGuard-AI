import shutil
import subprocess
from pathlib import Path

from floodguard.drainage.qa_viewer import QA_VIEWER_HTML


def test_qa_javascript_behavior(tmp_path: Path) -> None:
    node = shutil.which("node")
    assert node, "Node.js is required for the Sequence 8 QA behavior gate"
    html = tmp_path / "qa.html"
    html.write_text(QA_VIEWER_HTML, encoding="utf-8")
    result = subprocess.run(
        [node, str(Path(__file__).with_name("drain_qa_harness.cjs")), str(html)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS drain QA" in result.stdout
