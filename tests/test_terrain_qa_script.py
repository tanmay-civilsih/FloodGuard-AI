"""Run the page's real JavaScript with DOM/map doubles; no browser/CDN access required."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from floodguard.terrain.qa_viewer import QA_VIEWER_HTML


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is needed for QA script tests")
@pytest.mark.parametrize("scenario", [
    "normal", "empty", "http_error", "historical", "race", "acquire_success", "acquire_cached",
    "acquire_failed", "acquire_rejected", "acquire_expired",
])
def test_qa_javascript_behavior(scenario: str) -> None:
    script = re.findall(r"<script>(.*?)</script>", QA_VIEWER_HTML, flags=re.DOTALL)[0]
    node = shutil.which("node")
    assert node is not None
    result = subprocess.run(
        [node, str(Path(__file__).with_name("terrain_qa_harness.cjs"))],
        input=json.dumps({"script": script, "scenario": scenario}),
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert f"PASS {scenario}" in result.stdout
