"""A positive reference cannot hide failed verification or the inherited real-data gate."""

from scripts.sequence9_development_gate import twin_readiness_blockers
from scripts.sequence10_development_gate import readiness_errors


def ready():
    return dict(
        total_packages=1,
        verified_packages=1,
        eligible_packages=1,
        integrity_failures=[],
        assembly_development_gate_passed=True,
        operational_validation_claimed=False,
        final_human_acceptance_pending=True,
    )


def test_ready_forcing():
    assert readiness_errors(ready()) == []


def test_truthy_counts_and_acceptance_cannot_fake_readiness():
    for key in ("total_packages", "verified_packages", "eligible_packages"):
        for value in (True, "1", 0, -1, None):
            assert readiness_errors({**ready(), key: value})
    assert readiness_errors({**ready(), "operational_validation_claimed": True})
    assert readiness_errors({**ready(), "final_human_acceptance_pending": False})
    assert readiness_errors({**ready(), "verified_packages": 2})
    assert readiness_errors({**ready(), "integrity_failures": ["corrupt"]})


def test_real_data_gate_is_inherited_even_with_assembly_pass():
    blockers = twin_readiness_blockers(
        dict(
            current_pipeline_version="sequence-9-twin-v1",
            assembly_development_gate_passed=True,
            reference_scenario_ready=1,
            provisional_real_twins=1,
            real_cross_ward_twins=0,
            technical_development_gate_passed=False,
            final_completion_gate_passed=False,
            final_human_acceptance_pending=True,
        )
    )
    assert len(blockers) == 1
    assert "DATA-08-01" in blockers[0]
