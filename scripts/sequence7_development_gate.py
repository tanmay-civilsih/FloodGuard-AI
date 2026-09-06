"""Sequence 7 automated development gate with final human acceptance deferred to Sequence 20."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
HUMAN_REVIEW_SEQUENCE = 20
DEFERRED_HUMAN_REVIEW = [
    "Real-pilot visual-city geometry/source acceptance.",
    "Real-pilot hydraulic surface-class and hydraulic-domain acceptance.",
    "Every real roof's versioned receiving geometry or explicit drain-target acceptance.",
    "Real-browser comparison of exact visual/hydraulic/roof-runoff artifacts and limitations.",
]


def validate_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("base URL must be an HTTP(S) origin without credentials, path or query")
    return value.rstrip("/")


def command_ok(command: list[str]) -> bool:
    print("+", " ".join(command), flush=True)
    try:
        return subprocess.run(command, cwd=ROOT, check=False).returncode == 0
    except OSError:
        return False


def read_json(base: str, path: str) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(base + path, timeout=8) as response:
            payload = bytes(response.read(MAX_RESPONSE_BYTES + 1))
        if len(payload) > MAX_RESPONSE_BYTES:
            return None
        decoded: object = json.loads(payload)
    except (OSError, ValueError):
        return None
    if not isinstance(decoded, dict):
        return None
    return decoded


def urban_readiness_blockers(readiness: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if readiness.get("current_pipeline_version") != "sequence-7-urban-gis-v1":
        blockers.append("Sequence 7 pipeline identity mismatch.")
    if readiness.get("technical_development_gate_passed") is not True:
        blockers.append("Sequence 7 urban GIS automated development gate has not passed.")
    ready_total = 0
    for field in ("reference_ready", "provisional_real_ready", "reviewed_real_ready"):
        value = readiness.get(field)
        if not isinstance(value, int):
            blockers.append(f"Sequence 7 readiness field {field} is invalid.")
        else:
            ready_total += value
    if ready_total < 1:
        blockers.append("No current-pipeline Sequence 7 package is ready.")
    return blockers


def collect(base: str, *, run_checks: bool) -> dict[str, Any]:
    from floodguard.common.release_evidence import lock_mismatches, source_fingerprint

    blockers: list[str] = []
    report: dict[str, Any] = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "sequence": 7,
        "release": "0.7.0",
        "scope": "AUTOMATED_DEVELOPMENT_GATE_ONLY",
        "human_review_deferred_to_sequence": HUMAN_REVIEW_SEQUENCE,
        "deferred_human_review": DEFERRED_HUMAN_REVIEW.copy(),
        "final_human_acceptance_status": "PENDING_SEQUENCE_20",
    }
    if sys.version_info[:2] != (3, 12):
        blockers.append(f"Pinned Python 3.12 is required; found {sys.version.split()[0]}.")

    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        report["repository_commit"] = commit
        if dirty or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
            blockers.append("A clean, committed Git worktree is required.")
    except (OSError, subprocess.CalledProcessError):
        blockers.append("A complete Git checkout is unavailable.")

    try:
        fingerprint = source_fingerprint(ROOT)
        mismatches = lock_mismatches(ROOT / "requirements.lock")
        report["source_fingerprint"] = fingerprint
        report["dependency_lock_mismatches"] = mismatches
        if mismatches:
            blockers.append("Installed dependencies differ from requirements.lock.")
    except (OSError, ValueError, ImportError):
        fingerprint = None
        blockers.append("Local release-source or lockfile evidence is unavailable.")

    software_ok = False
    storage_ok = False
    if run_checks and not blockers:
        software_ok = command_ok(
            [sys.executable, "scripts/verify.py", "--services", "--urban-gis-bootstrap"]
        )
        if software_ok:
            storage_ok = command_ok(
                [
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "api",
                    "python",
                    "scripts/verify_storage.py",
                ]
            )
    report["software_and_services_passed"] = software_ok
    report["deployed_conditional_storage_passed"] = storage_ok
    if not software_ok:
        blockers.append("Full pinned-runtime Sequence 7 software/service gate has not passed.")
    if not storage_ok:
        blockers.append("Deployed conditional-storage gate has not passed for Sequence 7.")

    version = read_json(base, "/version")
    if version is None:
        blockers.append("Sequence 7 API version evidence is unavailable.")
    elif (
        version.get("sequence") != 7
        or version.get("version") != "0.7.0"
        or not str(version.get("runtime_python", "")).startswith("3.12.")
        or version.get("dependency_lock_mismatches") != []
        or fingerprint is None
        or version.get("source_fingerprint") != fingerprint
    ):
        blockers.append("Running API source/runtime identity does not match this Sequence 7 checkout.")

    readiness = read_json(base, "/urban-gis/readiness?city_id=kolkata")
    if readiness is None:
        blockers.append("Sequence 7 urban GIS readiness evidence is unavailable.")
    else:
        blockers.extend(urban_readiness_blockers(readiness))
        report["urban_gis_readiness"] = readiness

    report["technical_blockers"] = list(dict.fromkeys(blockers))
    passed = not report["technical_blockers"]
    report["development_status"] = "PASSED" if passed else "BLOCKED"
    report["technical_development_freeze_status"] = "ELIGIBLE" if passed else "NOT_ELIGIBLE"
    report["freeze_status"] = (
        "TECHNICAL_DEVELOPMENT_FREEZE_ELIGIBLE" if passed else "NOT_FROZEN"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--run-checks", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT.parent / "floodguard-sequence7-development-gate.json",
    )
    args = parser.parse_args()
    try:
        base = validate_base_url(args.base_url)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    report = collect(base, run_checks=args.run_checks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))
    print(f"Report: {args.output.resolve()}")
    raise SystemExit(1 if report["technical_blockers"] else 0)


if __name__ == "__main__":
    main()
