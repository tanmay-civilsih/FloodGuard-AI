from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from floodguard.common import release_evidence
from scripts import sequence7_development_gate as gate
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


@pytest.mark.parametrize("sequence", [6, 7, 8])
def test_file_entrypoint_can_import_repo_package(tmp_path: Path, sequence: int) -> None:
    output = tmp_path / "development-gate.json"
    result = subprocess.run(
        [
            sys.executable,
            f"scripts/sequence{sequence}_development_gate.py",
            "--base-url",
            "http://127.0.0.1:9",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "ModuleNotFoundError" not in result.stderr
    assert "No module named 'floodguard'" not in result.stderr
    assert result.returncode == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["development_status"] == "BLOCKED"
    assert report["freeze_status"] == "NOT_FROZEN"


@pytest.mark.parametrize("invalid_count", [True, -1, 1.0, "1", None])
def test_invalid_ready_count_cannot_pass(invalid_count: object) -> None:
    assert urban_readiness_blockers({
        "current_pipeline_version": "sequence-7-urban-gis-v1",
        "technical_development_gate_passed": True,
        "reference_ready": invalid_count,
        "provisional_real_ready": 0,
        "reviewed_real_ready": 0,
    })


@pytest.mark.parametrize("change", ["none", "source", "commit", "worktree"])
def test_gate_requires_the_same_clean_source_throughout(
    monkeypatch: pytest.MonkeyPatch, change: str,
) -> None:
    commit = "a" * 40
    git_outputs = iter([
        commit, "", "b" * 40 if change == "commit" else commit,
        " M apps/api/main.py" if change == "worktree" else "",
    ])
    fingerprints = iter(["initial", "changed" if change == "source" else "initial"])
    monkeypatch.setattr(gate.sys, "version_info", (3, 12, 10, "final", 0))
    monkeypatch.setattr(gate.subprocess, "check_output", lambda *a, **k: next(git_outputs))
    monkeypatch.setattr(release_evidence, "source_fingerprint", lambda root: next(fingerprints))
    monkeypatch.setattr(release_evidence, "lock_mismatches", lambda lock: [])
    monkeypatch.setattr(gate, "command_ok", lambda command: True)
    version = {
        "sequence": 7, "version": "0.7.0", "runtime_python": "3.12.11",
        "source_fingerprint": "initial", "dependency_lock_mismatches": [],
    }
    readiness = {
        "current_pipeline_version": "sequence-7-urban-gis-v1",
        "technical_development_gate_passed": True,
        "reference_ready": 1, "provisional_real_ready": 0, "reviewed_real_ready": 0,
    }
    monkeypatch.setattr(
        gate, "read_json", lambda base, path: version if path == "/version" else readiness,
    )
    report = gate.collect("http://localhost:8000", run_checks=True)
    assert report["development_status"] == ("PASSED" if change == "none" else "BLOCKED")
    assert report["final_human_acceptance_status"] == "PENDING_SEQUENCE_20"
