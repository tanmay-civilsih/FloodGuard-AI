import pytest

from floodguard.common import release_evidence
from scripts import sequence8_development_gate as gate
from scripts.sequence8_development_gate import drain_readiness_blockers


def ready():
    return {
        "current_pipeline_version": "sequence-8-drain-model-v1",
        "technical_development_gate_passed": True,
        "reference_ready": 1,
        "real_pilot_imports": 1,
        "final_completion_gate_passed": False,
        "final_human_acceptance_pending": True,
    }


def test_reference_and_real_import_pass_only_technical_gate() -> None:
    assert drain_readiness_blockers(ready()) == []


@pytest.mark.parametrize("field", ["reference_ready", "real_pilot_imports"])
@pytest.mark.parametrize("value", [0, -1, True, "1", 1.0, None])
def test_no_missing_or_invalid_evidence_counts(field, value) -> None:
    data = ready()
    data[field] = value
    assert drain_readiness_blockers(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("current_pipeline_version", "old"),
        ("technical_development_gate_passed", False),
        ("final_completion_gate_passed", True),
        ("final_human_acceptance_pending", False),
    ],
)
def test_false_status_or_pipeline_rejected(field, value) -> None:
    data = ready()
    data[field] = value
    assert drain_readiness_blockers(data)


@pytest.mark.parametrize("change", ["none", "source", "commit", "worktree", "artifact"])
def test_gate_requires_clean_unchanged_source_and_deployed_artifacts(monkeypatch, change) -> None:
    commit = "a" * 40
    git_outputs = iter(
        [
            commit,
            "",
            "b" * 40 if change == "commit" else commit,
            " M apps/api/main.py" if change == "worktree" else "",
        ]
    )
    fingerprints = iter(["initial", "changed" if change == "source" else "initial"])
    monkeypatch.setattr(gate.sys, "version_info", (3, 12, 10, "final", 0))
    monkeypatch.setattr(gate.subprocess, "check_output", lambda *a, **k: next(git_outputs))
    monkeypatch.setattr(release_evidence, "source_fingerprint", lambda root: next(fingerprints))
    monkeypatch.setattr(release_evidence, "lock_mismatches", lambda lock: [])
    monkeypatch.setattr(gate, "command_ok", lambda command: True)
    version = {
        "sequence": 8,
        "version": "0.8.0",
        "runtime_python": "3.12.11",
        "source_fingerprint": "initial",
        "dependency_lock_mismatches": [],
    }
    monkeypatch.setattr(
        gate, "read_json", lambda base, path: version if path == "/version" else ready()
    )

    def readback(base):
        if change == "artifact":
            raise ValueError("corrupt artifact")
        return [{"http_readback_verified": True}]

    monkeypatch.setattr(gate, "product_evidence", readback)
    report = gate.collect("http://localhost:8000", run_checks=True)
    assert report["development_status"] == ("PASSED" if change == "none" else "BLOCKED")
    assert report["final_human_acceptance_status"] == "PENDING_SEQUENCE_20"
