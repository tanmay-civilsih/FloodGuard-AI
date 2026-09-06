"""Policy tests for the owner-approved Sequence 20 human-review deferral."""

from scripts.sequence6_development_gate import classify_for_development


def base_report() -> dict[str, object]:
    return {
        "technical_status": "BLOCKED",
        "technical_blockers": [
            "Selected pilot terrain is not scenario-ready.",
            "An immutable terrain assessment is missing.",
        ],
        "engineering_acceptance_remaining": [
            "Independent cross-layer alignment evidence bound to the current normalized products.",
            (
                "Real-browser QA of the selected artifacts and explicit acceptance of "
                "coarse-data limitations."
            ),
        ],
    }


def test_missing_human_terrain_review_does_not_block_development() -> None:
    report = classify_for_development(base_report())
    assert report["development_blockers"] == []
    assert report["development_status"] == "PASSED"
    assert report["technical_status"] == "PASSED_FOR_DEVELOPMENT"
    assert report["technical_development_freeze_status"] == "ELIGIBLE"
    assert report["freeze_status"] == "TECHNICAL_DEVELOPMENT_FREEZE_ELIGIBLE"
    assert report["final_human_acceptance_status"] == "PENDING_SEQUENCE_20"
    assert report["human_review_deferred_to_sequence"] == 20
    assert "An immutable terrain assessment is missing." in report["deferred_human_review"]


def test_automated_failure_remains_a_development_blocker() -> None:
    source = base_report()
    source["technical_blockers"] = [
        *source["technical_blockers"],
        "Deployed conditional-storage gate has not passed in this run.",
    ]
    report = classify_for_development(source)
    assert report["development_status"] == "BLOCKED"
    assert report["technical_development_freeze_status"] == "NOT_ELIGIBLE"
    assert report["development_blockers"] == [
        "Deployed conditional-storage gate has not passed in this run."
    ]


def test_low_terrain_readiness_without_human_context_stays_blocking() -> None:
    source = base_report()
    source["technical_blockers"] = ["Selected pilot terrain is not scenario-ready."]
    report = classify_for_development(source)
    assert report["development_blockers"] == [
        "Selected pilot terrain is not scenario-ready."
    ]
    assert report["development_status"] == "BLOCKED"


def test_partial_human_assessment_fields_are_deferred() -> None:
    source = base_report()
    source["technical_blockers"] = [
        "Selected pilot terrain is not scenario-ready.",
        "Terrain assessment lacks reviewed_by.",
        "Terrain assessment is incomplete: depression_assessment.",
        "Terrain review time is not a timezone-aware timestamp.",
    ]
    report = classify_for_development(source)
    assert report["development_blockers"] == []
    assert all(
        item in report["deferred_human_review"]
        for item in source["technical_blockers"]
    )


def test_invalid_datum_claim_is_not_deferred() -> None:
    source = base_report()
    source["technical_blockers"] = [
        "Selected pilot terrain is not scenario-ready.",
        "Terrain assessment lacks reviewed_by.",
        "Compatible SRTM assessment must identify local EGM96 compatibility.",
    ]
    report = classify_for_development(source)
    assert report["development_blockers"] == [
        "Compatible SRTM assessment must identify local EGM96 compatibility."
    ]


def test_manual_register_remains_pending_even_when_automated_gate_is_clean() -> None:
    source = base_report()
    source["technical_status"] = "PASSED_PENDING_ENGINEERING_ACCEPTANCE"
    source["technical_blockers"] = []
    report = classify_for_development(source)
    assert report["development_status"] == "PASSED"
    assert report["final_human_acceptance_status"] == "PENDING_SEQUENCE_20"
    assert report["deferred_human_review"] == source["engineering_acceptance_remaining"]
