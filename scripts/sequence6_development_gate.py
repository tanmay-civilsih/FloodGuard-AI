"""Sequence 6 automated development gate with final human acceptance deferred to Sequence 20."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.sequence6_preflight import collect, validate_base_url

HUMAN_REVIEW_SEQUENCE = 20
HUMAN_TERRAIN_PREFIXES = (
    "Terrain assessment lacks ",
    "Terrain assessment is incomplete: ",
)
HUMAN_TERRAIN_MESSAGES = {
    "An immutable terrain assessment is missing.",
    "Terrain review time is not a timezone-aware timestamp.",
}
SCENARIO_READINESS_MESSAGE = "Selected pilot terrain is not scenario-ready."


def _direct_human_blocker(message: str) -> bool:
    return message in HUMAN_TERRAIN_MESSAGES or message.startswith(HUMAN_TERRAIN_PREFIXES)


def classify_for_development(preflight: dict[str, Any]) -> dict[str, Any]:
    """Separate automatable development blockers from explicitly deferred human review.

    The underlying preflight remains conservative and unchanged. This overlay is intentionally
    narrow: only known human terrain-assessment items are deferred. A low terrain readiness state
    is deferred only when one of those human assessment blockers is also present; otherwise it
    remains a development blocker because an automated validation failure may be responsible.
    """
    raw_blockers = preflight.get("technical_blockers")
    if not isinstance(raw_blockers, list) or any(not isinstance(item, str) for item in raw_blockers):
        raise ValueError("preflight technical_blockers must be a list of strings")
    manual = preflight.get("engineering_acceptance_remaining", [])
    if not isinstance(manual, list) or any(not isinstance(item, str) for item in manual):
        raise ValueError("engineering_acceptance_remaining must be a list of strings")

    direct_human = [message for message in raw_blockers if _direct_human_blocker(message)]
    human_context = bool(direct_human)
    deferred: list[str] = []
    development_blockers: list[str] = []
    for message in raw_blockers:
        if _direct_human_blocker(message):
            deferred.append(message)
        elif message == SCENARIO_READINESS_MESSAGE and human_context:
            deferred.append(message)
        else:
            development_blockers.append(message)

    deferred.extend(manual)
    deferred = list(dict.fromkeys(deferred))
    development_blockers = list(dict.fromkeys(development_blockers))

    report = dict(preflight)
    report["pre_deferral_technical_status"] = preflight.get("technical_status")
    report["pre_deferral_technical_blockers"] = raw_blockers
    report["human_review_deferred_to_sequence"] = HUMAN_REVIEW_SEQUENCE
    report["development_gate_policy"] = (
        "AUTOMATED_SEQUENCE_GATE_WITH_CONSOLIDATED_HUMAN_ACCEPTANCE_AT_SEQUENCE_20"
    )
    report["development_blockers"] = development_blockers
    report["deferred_human_review"] = deferred
    report["final_acceptance_blockers"] = deferred
    report["technical_blockers"] = development_blockers
    report["development_status"] = "PASSED" if not development_blockers else "BLOCKED"
    report["technical_status"] = (
        "PASSED_FOR_DEVELOPMENT" if not development_blockers else "BLOCKED"
    )
    report["technical_development_freeze_status"] = (
        "ELIGIBLE" if not development_blockers else "NOT_ELIGIBLE"
    )
    report["freeze_status"] = (
        "TECHNICAL_DEVELOPMENT_FREEZE_ELIGIBLE"
        if not development_blockers
        else "NOT_FROZEN"
    )
    report["final_human_acceptance_status"] = (
        "PENDING_SEQUENCE_20" if deferred else "READY_FOR_FINAL_ACCEPTANCE"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--city-id", default="kolkata")
    parser.add_argument("--ward-id", default="7")
    parser.add_argument("--run-checks", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "floodguard-sequence6-development-gate.json",
    )
    args = parser.parse_args()
    try:
        base = validate_base_url(args.base_url)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    preflight = collect(base, city=args.city_id, ward=args.ward_id, run_checks=args.run_checks)
    report = classify_for_development(preflight)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))
    print(f"Report: {args.output.resolve()}")
    raise SystemExit(1 if report["development_blockers"] else 0)


if __name__ == "__main__":
    main()
