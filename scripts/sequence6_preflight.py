"""Collect Sequence 6 acceptance evidence without approving maps or freezing a release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MAX_RESPONSE_BYTES = 128 * 1024 * 1024
MANUAL_ACCEPTANCE = [
    "Independent cross-layer alignment evidence bound to the current normalized products.",
    "Engineering review of the exact terrain audit, depression and multi-level assessments.",
    "Review provenance for the selected reconstruction, including any pre-authentication approval.",
    "Real-browser QA of the selected artifacts and explicit acceptance of coarse-data limitations.",
]


def validate_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
        or parsed.username or parsed.password or parsed.query or parsed.fragment
        or parsed.path not in {"", "/"}):
        raise ValueError("base URL must be an HTTP(S) origin without credentials, path or query")
    return value.rstrip("/")


def read_bytes(base: str, path: str) -> bytes:
    with urllib.request.urlopen(base + path, timeout=8) as response:
        data = bytes(response.read(MAX_RESPONSE_BYTES + 1))
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("API response exceeds the bounded preflight limit")
    return data


def select_product(
    products: list[dict[str, Any]], *, pilot: str, pipeline: str,
) -> dict[str, Any] | None:
    if any(not isinstance(item, dict) for item in products):
        raise ValueError("terrain inventory must contain objects")
    candidates = [
        item for item in products
        if item.get("pilot_area_id") == pilot and item.get("pipeline_version") == pipeline
    ]
    if not candidates:
        return None

    def order(item: dict[str, Any]) -> tuple[datetime, str]:
        created = datetime.fromisoformat(str(item["created_at"]).replace("Z", "+00:00"))
        if created.tzinfo is None:
            raise ValueError("terrain timestamps must be timezone-aware")
        return created.astimezone(UTC), str(UUID(str(item["terrain_id"])))

    return max(candidates, key=order)


def terrain_blockers(
    product: dict[str, Any], audit: dict[str, Any], plan: dict[str, Any],
) -> list[str]:
    blockers = []
    if product.get("pilot_area_id") != plan.get("pilot_area_id"):
        blockers.append("Selected terrain does not belong to the requested pilot.")
    if product.get("readiness_status") not in {"HYDRAULIC_SCENARIO_READY", "HYDRAULIC_VALIDATED"}:
        blockers.append("Selected pilot terrain is not scenario-ready.")
    if audit.get("terrain_id") != product.get("terrain_id"):
        blockers.append("Audit does not identify the selected terrain.")
    if audit.get("readiness_status") != product.get("readiness_status"):
        blockers.append("Audit and terrain readiness disagree.")
    if audit.get("pipeline_version") != product.get("pipeline_version"):
        blockers.append("Audit and terrain pipeline policy disagree.")
    derivation = audit.get("derivation")
    if not isinstance(derivation, dict) or (
        derivation.get("boundary_reference") != plan.get("boundary_reference")
    ):
        blockers.append("Terrain is not bound to the currently approved reconstruction.")
    assessment = audit.get("terrain_assessment")
    if not isinstance(assessment, dict):
        return [*blockers, "An immutable terrain assessment is missing."]
    for field in ("reviewed_by", "reviewed_at", "vertical_reference_evidence",
                  "surface_use_evidence",
                  "depression_evidence", "multi_level_evidence"):
        if not isinstance(assessment.get(field), str) or not assessment[field].strip():
            blockers.append(f"Terrain assessment lacks {field}.")
    for field in ("depression_assessment", "multi_level_assessment"):
        if assessment.get(field) not in {"CATALOGUED", "CONFIRMED_NONE"}:
            blockers.append(f"Terrain assessment is incomplete: {field}.")
    if (assessment.get("datum_transform_status") != "COMPATIBLE"
        or assessment.get("local_vertical_datum") != "EGM96"):
        blockers.append("Local vertical-reference compatibility is unresolved.")
    try:
        reviewed = datetime.fromisoformat(str(assessment.get("reviewed_at")).replace("Z", "+00:00"))
        if reviewed.tzinfo is None:
            raise ValueError("review time lacks a timezone")
    except ValueError:
        blockers.append("Terrain review time is not a timezone-aware timestamp.")
    return blockers


def command_ok(command: list[str]) -> bool:
    print("+", " ".join(command), flush=True)
    try:
        return subprocess.run(command, cwd=ROOT, check=False).returncode == 0
    except OSError:
        return False


def collect(base: str, *, city: str, ward: str, run_checks: bool) -> dict[str, Any]:
    from floodguard.common.release_evidence import lock_mismatches, source_fingerprint

    blockers: list[str] = []
    report: dict[str, Any] = {"schema_version": 1, "created_at": datetime.now(UTC).isoformat(),
                              "freeze_status": "NOT_FROZEN", "city_id": city, "ward_id": ward,
                              "scope": "CURRENT_EXECUTION_ENVIRONMENT_ONLY",
                              "local_python": sys.version.split()[0], "api_origin": base,
                              "engineering_acceptance_remaining": MANUAL_ACCEPTANCE.copy()}
    if sys.version_info[:2] != (3, 12):
        blockers.append(f"Pinned Python 3.12 is required; found {sys.version.split()[0]}.")
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                         text=True, stderr=subprocess.DEVNULL).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT,
                                        text=True, stderr=subprocess.DEVNULL).strip()
        report["repository_commit"] = commit
        if dirty or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
            blockers.append("A clean, committed Git worktree is required.")
    except (OSError, subprocess.CalledProcessError):
        blockers.append("A complete Git checkout is unavailable.")
    try:
        report["source_fingerprint"] = source_fingerprint(ROOT)
        report["dependency_lock_mismatches"] = lock_mismatches(ROOT / "requirements.lock")
        if report["dependency_lock_mismatches"]:
            blockers.append("Installed dependencies differ from requirements.lock.")
    except (OSError, ValueError, ImportError):
        blockers.append("Local release-source or lockfile evidence is unavailable.")
    if shutil.which("node") is None:
        blockers.append("Node.js is required for the terrain-viewer behavior tests at acceptance.")
    software_ok = False
    storage_ok = False
    if run_checks and not blockers:
        software_ok = command_ok([sys.executable, "scripts/verify.py", "--services"])
        if software_ok:
            storage_ok = command_ok(["docker", "compose", "exec", "-T", "api", "python",
                                     "scripts/verify_storage.py"])
    report["software_and_services_passed"] = software_ok
    report["deployed_conditional_storage_passed"] = storage_ok
    if not software_ok:
        blockers.append("Full pinned-runtime software/service gate has not passed in this run.")
    if not storage_ok:
        blockers.append("Deployed conditional-storage gate has not passed in this run.")

    def get(path: str) -> Any:
        try:
            return json.loads(read_bytes(base, path))
        except (OSError, ValueError):
            blockers.append(f"Required API evidence unavailable: {path}")
            return None

    ready = get("/ready")
    if not isinstance(ready, dict) or ready.get("status") != "ready":
        blockers.append("API dependency readiness was not verified in this run.")
    version = get("/version")
    if not isinstance(version, dict) or version.get("sequence") != 6:
        blockers.append("The running API Sequence 6 identity was not verified in this run.")
    elif (not report.get("source_fingerprint")
          or version.get("source_fingerprint") != report["source_fingerprint"]
          or not str(version.get("runtime_python", "")).startswith("3.12.")
          or version.get("dependency_lock_mismatches") != []):
        blockers.append("Running API source/runtime does not match this pinned checkout.")
    query = urlencode({"city_id": city})
    spatial = get("/spatial/readiness?" + query)
    if (not isinstance(spatial, dict) or spatial.get("numerical_roundtrip_check_passed") is not True
        or spatial.get("missing_core_categories") != []):
        blockers.append("Current spatial products have not passed numerical preparation checks.")
    reconstruction = get("/reconstruction/readiness?" + query)
    if (not isinstance(reconstruction, dict)
        or reconstruction.get("completion_gate_passed") is not True):
        blockers.append("The reconstruction completion gate was not verified in this run.")
    terrain = get("/terrain/readiness?" + query)
    plan = get("/terrain/acquisition/plan?" + urlencode({"city_id": city, "ward_id": ward}))
    products = get("/terrain/products?" + query)
    if isinstance(terrain, dict) and isinstance(plan, dict) and isinstance(products, list):
        try:
            product = select_product(products, pilot=str(plan["pilot_area_id"]),
                                     pipeline=str(terrain["current_pipeline_version"]))
            if product is None:
                blockers.append("No current-policy product exists for the selected pilot.")
            else:
                terrain_id = str(UUID(str(product["terrain_id"])))
                report["terrain_id"] = terrain_id
                report["terrain_pipeline"] = product["pipeline_version"]
                verified: dict[str, str] = {}
                audit: dict[str, Any] = {}
                for suffix, field in (("raw", "raw_elevation_sha256"),
                                      ("visual", "visual_terrain_sha256"),
                                      ("hydraulic", "hydraulic_terrain_sha256"),
                                      ("multi-level-structures", "multi_level_sha256"),
                                      ("qa", "qa_sha256"), ("audit", "audit_sha256")):
                    payload = read_bytes(base, f"/terrain/products/{terrain_id}/{suffix}")
                    digest = hashlib.sha256(payload).hexdigest()
                    if digest != product.get(field):
                        raise ValueError(f"{suffix} artifact hash does not match its record")
                    verified[suffix] = digest
                    if suffix == "audit":
                        audit = json.loads(payload)
                report["verified_artifact_hashes"] = verified
                if not isinstance(audit, dict):
                    raise ValueError("terrain audit must be an object")
                blockers.extend(terrain_blockers(product, audit, plan))
                current_plan = get("/terrain/acquisition/plan?" + urlencode({
                    "city_id": city, "ward_id": ward,
                }))
                if current_plan != plan:
                    blockers.append("Approved reconstruction changed during evidence collection.")
                current_products = get("/terrain/products?" + query)
                if not isinstance(current_products, list) or select_product(
                    current_products, pilot=str(plan["pilot_area_id"]),
                    pipeline=str(terrain["current_pipeline_version"]),
                ) != product:
                    blockers.append(
                        "Selected terrain inventory changed during evidence collection."
                    )
        except (KeyError, TypeError, ValueError, OSError) as exc:
            blockers.append(
                f"Selected terrain evidence could not be verified: {type(exc).__name__}"
            )
    else:
        blockers.append("Selected-pilot terrain evidence is unavailable.")
    if report.get("source_fingerprint"):
        try:
            if source_fingerprint(ROOT) != report["source_fingerprint"]:
                blockers.append("Release sources changed during preflight.")
            current_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL,
            ).strip()
            dirty_after = subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL,
            ).strip()
            if current_commit != report.get("repository_commit") or dirty_after:
                blockers.append("Git checkout changed or became dirty during preflight.")
        except (OSError, ValueError, subprocess.CalledProcessError):
            blockers.append("Final source snapshot could not be verified.")
    report["technical_blockers"] = list(dict.fromkeys(blockers))
    report["technical_status"] = "BLOCKED" if blockers else "PASSED_PENDING_ENGINEERING_ACCEPTANCE"
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--city-id", default="kolkata")
    parser.add_argument("--ward-id", default="7")
    parser.add_argument("--run-checks", action="store_true")
    parser.add_argument("--output", type=Path,
                        default=ROOT.parent / "floodguard-sequence6-preflight.json")
    args = parser.parse_args()
    try:
        base = validate_base_url(args.base_url)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    report = collect(base, city=args.city_id, ward=args.ward_id, run_checks=args.run_checks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))
    print(f"Report: {args.output.resolve()}")
    raise SystemExit(1 if report["technical_blockers"] else 0)


if __name__ == "__main__":
    main()
