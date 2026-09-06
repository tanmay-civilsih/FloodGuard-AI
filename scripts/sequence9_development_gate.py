"""Sequence 9 automated development gate with final human acceptance deferred to Sequence 20."""

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
sys.path.insert(0, str(ROOT))
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
HUMAN_REVIEW_SEQUENCE = 20
DEFERRED_HUMAN_REVIEW = [
    "Acceptance of exact real pilot component selections and missing-data limitations.",
    "Cross-component geographic and vertical-reference engineering acceptance.",
    "Visual review of immutable manifests and their real source artifacts.",
]
REAL_PILOT_CONSTRAINT = (
    "DATA-08-01: genuine source-bound adjacent-ward drainage to a defensible destination "
    "is mandatory for Sequence 9 technical freeze; human review deferral does not waive it."
)


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


def twin_readiness_blockers(readiness: dict[str, Any]) -> list[str]:
    blockers = []
    if readiness.get("current_pipeline_version") != "sequence-9-twin-v1":
        blockers.append("Sequence 9 pipeline identity mismatch.")
    if readiness.get("assembly_development_gate_passed") is not True:
        blockers.append("Twin assembly and recreation gate has not passed.")
    for field in ("reference_scenario_ready", "provisional_real_twins"):
        value = readiness.get(field)
        if type(value) is not int or value < 1:
            blockers.append(f"A verified {field} twin is required.")
    cross = readiness.get("real_cross_ward_twins")
    if type(cross) is not int or cross < 1:
        blockers.append(REAL_PILOT_CONSTRAINT)
    if (
        readiness.get("technical_development_gate_passed") is not True
        and REAL_PILOT_CONSTRAINT not in blockers
    ):
        blockers.append("Sequence 9 technical freeze gate has not passed.")
    if readiness.get("final_completion_gate_passed") is not False:
        blockers.append("Final scientific acceptance cannot be inferred by twin assembly.")
    if readiness.get("final_human_acceptance_pending") is not True:
        blockers.append("Final human acceptance must remain explicit.")
    return blockers


def product_evidence(base: str, source_sha: str | None) -> list[dict[str, Any]]:
    from floodguard.common.integrity import verified_payload
    from floodguard.twin.contracts import ComponentRole, TwinManifest, TwinProductRead

    def read(path: str, limit: int = 128 * 1024 * 1024) -> bytes:
        with urllib.request.urlopen(base + path, timeout=60) as response:
            payload = bytes(response.read(limit + 1))
        if len(payload) > limit:
            raise ValueError("twin HTTP artifact exceeds readback limit")
        return payload

    products = json.loads(read("/twins/products?city_id=kolkata", MAX_RESPONSE_BYTES))
    if not isinstance(products, list):
        raise ValueError("twin inventory must be a list")
    evidence = []
    for item in products:
        record = TwinProductRead.model_validate(item)
        prefix = f"/twins/products/{record.twin_id}/"
        raw = read(prefix + "manifest")
        verified_payload(
            raw,
            expected_sha256=record.manifest.sha256,
            expected_size=record.manifest.byte_size,
            max_bytes=128 * 1024 * 1024,
        )
        manifest = TwinManifest.model_validate_json(raw)
        if manifest.software_source_sha256 != source_sha:
            continue
        verified_payload(
            read(prefix + "audit"),
            expected_sha256=record.audit.sha256,
            expected_size=record.audit.byte_size,
            max_bytes=128 * 1024 * 1024,
        )
        count = 2
        for role in ComponentRole:
            component = manifest.component(role)
            if component.artifact is None:
                continue
            verified_payload(
                read(prefix + role.value),
                expected_sha256=component.artifact.sha256,
                expected_size=component.artifact.byte_size,
                max_bytes=128 * 1024 * 1024,
            )
            count += 1
        evidence.append(
            {
                **record.model_dump(mode="json"),
                "http_readback_artifacts": count,
                "manifest": manifest.model_dump(mode="json"),
                "frozen_evidence_artifacts": len(manifest.evidence_artifacts),
                "http_readback_verified": True,
            }
        )
    if len(evidence) < 2:
        raise ValueError("current-source reference and real twin readback is required")
    return evidence


def collect(base: str, *, run_checks: bool) -> dict[str, Any]:
    from floodguard.common.release_evidence import lock_mismatches, source_fingerprint

    blockers: list[str] = []
    report: dict[str, Any] = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "sequence": 9,
        "release": "0.9.0",
        "scope": "AUTOMATED_DEVELOPMENT_GATE_ONLY",
        "human_review_deferred_to_sequence": HUMAN_REVIEW_SEQUENCE,
        "deferred_human_review": DEFERRED_HUMAN_REVIEW.copy(),
        "final_human_acceptance_status": "PENDING_SEQUENCE_20",
        "real_pilot_constraint": REAL_PILOT_CONSTRAINT,
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
            [sys.executable, "scripts/verify.py", "--services", "--twin-bootstrap"]
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
        blockers.append("Full pinned-runtime Sequence 9 software/service gate has not passed.")
    if not storage_ok:
        blockers.append("Deployed conditional-storage gate has not passed for Sequence 9.")

    version = read_json(base, "/version")
    if version is None:
        blockers.append("Sequence 9 API version evidence is unavailable.")
    elif (
        version.get("sequence") != 9
        or version.get("version") != "0.9.0"
        or not str(version.get("runtime_python", "")).startswith("3.12.")
        or version.get("dependency_lock_mismatches") != []
        or fingerprint is None
        or version.get("source_fingerprint") != fingerprint
    ):
        blockers.append(
            "Running API source/runtime identity does not match this Sequence 9 checkout."
        )

    readiness = read_json(base, "/twins/readiness?city_id=kolkata")
    if readiness is None:
        blockers.append("Sequence 9 twin assembly readiness evidence is unavailable.")
    else:
        blockers.extend(twin_readiness_blockers(readiness))
        report["twin_readiness"] = readiness

    try:
        report["twin_products"] = product_evidence(base, fingerprint)
    except (OSError, ValueError, KeyError) as exc:
        blockers.append(f"Sequence 9 product HTTP readback failed: {type(exc).__name__}.")

    if fingerprint is not None:
        try:
            if source_fingerprint(ROOT) != fingerprint:
                blockers.append("Release source changed during the development gate.")
        except (OSError, ValueError):
            blockers.append("Release source became unavailable during the development gate.")
    if report.get("repository_commit"):
        try:
            commit_after = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
            ).strip()
            dirty_after = subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=ROOT,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            if commit_after != report["repository_commit"] or dirty_after:
                blockers.append("Git checkout changed or became dirty during the development gate.")
        except (OSError, subprocess.CalledProcessError):
            blockers.append("Git evidence became unavailable during the development gate.")

    report["technical_blockers"] = list(dict.fromkeys(blockers))
    report["assembly_validation_status"] = (
        "PASSED" if not [b for b in blockers if b != REAL_PILOT_CONSTRAINT] else "BLOCKED"
    )
    passed = not report["technical_blockers"]
    report["development_status"] = "PASSED" if passed else "BLOCKED"
    report["technical_development_freeze_status"] = "ELIGIBLE" if passed else "NOT_ELIGIBLE"
    report["freeze_status"] = "TECHNICAL_DEVELOPMENT_FREEZE_ELIGIBLE" if passed else "NOT_FROZEN"
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--run-checks", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "validation" / "sequence9-development-gate.json",
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
