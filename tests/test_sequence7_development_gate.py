from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.sequence7_development_gate import urban_readiness_blockers

ROOT = Path(__file__).resolve().parents[1]


def test_reference_ready_passes_without_final_human_acceptance() -> None:
    payload = {
        "current_pipeline_version": "sequence-7-urban-gis-v1",
        "technical_development_gate_passed": True,
        "reference_ready": 1,
        "provisional_real_ready": 0,
        "reviewed_real_ready": 0,
        "final_completion_gate_passed": False,
    }
    assert urban_readiness_blockers(payload) == []


def test_missing_ready_package_blocks() -> None:
    payload = {
        "current_pipeline_version": "sequence-7-urban-gis-v1",
        "technical_development_gate_passed": False,
        "reference_ready": 0,
        "provisional_real_ready": 0,
        "reviewed_real_ready": 0,
    }
    assert urban_readiness_blockers(payload)


def test_wrong_pipeline_blocks_even_if_reference_exists() -> None:
    payload = {
        "current_pipeline_version": "old-policy",
        "technical_development_gate_passed": True,
        "reference_ready": 1,
        "provisional_real_ready": 0,
        "reviewed_real_ready": 0,
    }
    assert urban_readiness_blockers(payload)


def test_file_entrypoint_can_import_repo_package() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/sequence7_development_gate.py",
            "--base-url",
            "http://127.0.0.1:9",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "ModuleNotFoundError" not in result.stderr
    assert "No module named 'floodguard'" not in result.stderr
