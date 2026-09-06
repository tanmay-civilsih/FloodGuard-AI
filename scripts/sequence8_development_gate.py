"""Sequence 8 automated development gate with final human acceptance deferred to Sequence 20."""

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
    "Real node classification, connectivity and direction evidence acceptance.",
    "Real dimensions, inverts, roughness, condition, capacity and vertical datum acceptance.",
    "Real pump/storage/outfall and physical exchange engineering acceptance.",
    "Exact immutable source/model/browser comparison and limitations acceptance.",
]
REAL_PILOT_CONSTRAINT = (
    "Real adjacent-ward continuation to a defensible downstream destination must be "
    "established before Sequence 9 is complete; a reference fixture does not satisfy it."
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


def drain_readiness_blockers(readiness: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if readiness.get("current_pipeline_version") != "sequence-8-drain-model-v1":
        blockers.append("Sequence 8 pipeline identity mismatch.")
    if readiness.get("technical_development_gate_passed") is not True:
        blockers.append("Sequence 8 drain model automated development gate has not passed.")
    for field in ("reference_ready", "real_pilot_imports"):
        value = readiness.get(field)
        if type(value) is not int or value < 1:
            blockers.append(f"Sequence 8 requires at least one verified {field} product.")
    if readiness.get("final_completion_gate_passed") is not False:
        blockers.append("Final completion must remain false until authorized acceptance exists.")
    if readiness.get("final_human_acceptance_pending") is not True:
        blockers.append("Final human acceptance must remain explicitly pending.")
    return blockers


def product_evidence(base: str) -> list[dict[str, Any]]:
    """Read every current product artifact over HTTP and retain exact immutable anchors."""
    from floodguard.common.integrity import verified_payload
    from floodguard.drainage.model_contracts import DRAIN_MODEL_PIPELINE_VERSION, DrainProductRead

    with urllib.request.urlopen(base + "/drainage/products?city_id=kolkata", timeout=8) as response:
        payload = bytes(response.read(MAX_RESPONSE_BYTES + 1))
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ValueError("drain product inventory exceeds gate response limit")
    products = json.loads(payload)
    if not isinstance(products, list):
        raise ValueError("drain product inventory must be a list")
    evidence = []
    for data in products:
        product = DrainProductRead.model_validate(data)
        if product.pipeline_version != DRAIN_MODEL_PIPELINE_VERSION:
            continue
        if product.city_id != "kolkata" or product.working_crs != "EPSG:32645":
            raise ValueError("current drain product city/CRS mismatch")
        for name, artifact in product.artifacts.items():
            if re.fullmatch(r"[a-z-]+", name) is None:
                raise ValueError("invalid drain artifact name")
            path = f"/drainage/products/{product.product_id}/{name}"
            with urllib.request.urlopen(base + path, timeout=15) as response:
                content = bytes(response.read(MAX_RESPONSE_BYTES + 1))
            verified_payload(
                content,
                expected_sha256=artifact.sha256,
                expected_size=artifact.byte_size,
                max_bytes=MAX_RESPONSE_BYTES,
            )
        evidence.append({**product.model_dump(mode="json"), "http_readback_verified": True})
    if not evidence:
        raise ValueError("no current drain artifacts were verified")
    return evidence


def collect(base: str, *, run_checks: bool) -> dict[str, Any]:
    from floodguard.common.release_evidence import lock_mismatches, source_fingerprint

    blockers: list[str] = []
    report: dict[str, Any] = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "sequence": 8,
        "release": "0.8.0",
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
            [sys.executable, "scripts/verify.py", "--services", "--drainage-bootstrap"]
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
        blockers.append("Full pinned-runtime Sequence 8 software/service gate has not passed.")
    if not storage_ok:
        blockers.append("Deployed conditional-storage gate has not passed for Sequence 8.")

    version = read_json(base, "/version")
    if version is None:
        blockers.append("Sequence 8 API version evidence is unavailable.")
    elif (
        version.get("sequence") != 8
        or version.get("version") != "0.8.0"
        or not str(version.get("runtime_python", "")).startswith("3.12.")
        or version.get("dependency_lock_mismatches") != []
        or fingerprint is None
        or version.get("source_fingerprint") != fingerprint
    ):
        blockers.append(
            "Running API source/runtime identity does not match this Sequence 8 checkout."
        )

    readiness = read_json(base, "/drainage/readiness?city_id=kolkata")
    if readiness is None:
        blockers.append("Sequence 8 drain model readiness evidence is unavailable.")
    else:
        blockers.extend(drain_readiness_blockers(readiness))
        report["drainage_readiness"] = readiness

    try:
        report["drainage_products"] = product_evidence(base)
    except (OSError, ValueError, KeyError) as exc:
        blockers.append(f"Sequence 8 product HTTP readback failed: {type(exc).__name__}.")

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
        default=ROOT / "artifacts" / "validation" / "sequence8-development-gate.json",
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
