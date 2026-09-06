import pytest

from floodguard.common import release_evidence
from scripts import sequence9_development_gate as gate


def ready(cross=1):
    return {
        "current_pipeline_version": "sequence-9-twin-v1",
        "assembly_development_gate_passed": True,
        "technical_development_gate_passed": bool(cross),
        "reference_scenario_ready": 1,
        "provisional_real_twins": 1,
        "real_cross_ward_twins": cross,
        "final_completion_gate_passed": False,
        "final_human_acceptance_pending": True,
    }


def test_real_cross_ward_evidence_cannot_be_deferred_with_human_review() -> None:
    assert gate.twin_readiness_blockers(ready(0)) == [gate.REAL_PILOT_CONSTRAINT]
    assert gate.twin_readiness_blockers(ready()) == []


@pytest.mark.parametrize(
    "field", ["reference_scenario_ready", "provisional_real_twins", "real_cross_ward_twins"]
)
@pytest.mark.parametrize("value", [True, 0, -1, 1.0, "1", None])
def test_invalid_evidence_counts_cannot_pass(field, value) -> None:
    data = ready()
    data[field] = value
    assert gate.twin_readiness_blockers(data)


@pytest.mark.parametrize(
    "change", ["none", "source", "commit", "worktree", "artifact", "real_cross"]
)
def test_gate_preserves_exact_source_and_separate_freeze_claims(monkeypatch, change) -> None:
    commit = "a" * 40
    outputs = iter(
        [
            commit,
            "",
            "b" * 40 if change == "commit" else commit,
            " M apps/api/main.py" if change == "worktree" else "",
        ]
    )
    fingerprints = iter(["initial", "changed" if change == "source" else "initial"])
    monkeypatch.setattr(gate.sys, "version_info", (3, 12, 10, "final", 0))
    monkeypatch.setattr(gate.subprocess, "check_output", lambda *a, **k: next(outputs))
    monkeypatch.setattr(release_evidence, "source_fingerprint", lambda root: next(fingerprints))
    monkeypatch.setattr(release_evidence, "lock_mismatches", lambda lock: [])
    monkeypatch.setattr(gate, "command_ok", lambda command: True)
    version = {
        "sequence": 9,
        "version": "0.9.0",
        "runtime_python": "3.12.11",
        "source_fingerprint": "initial",
        "dependency_lock_mismatches": [],
    }
    monkeypatch.setattr(
        gate,
        "read_json",
        lambda base, path: version
        if path == "/version"
        else ready(0 if change == "real_cross" else 1),
    )

    def readback(*args):
        if change == "artifact":
            raise ValueError("bad artifact")
        return [{"http_readback_verified": True}]

    monkeypatch.setattr(gate, "product_evidence", readback)
    report = gate.collect("http://localhost:8000", run_checks=True)
    assert report["development_status"] == ("PASSED" if change == "none" else "BLOCKED")
    assert report["assembly_validation_status"] == (
        "PASSED" if change in {"none", "real_cross"} else "BLOCKED"
    )
    if change == "real_cross":
        assert report["freeze_status"] == "NOT_FROZEN"
