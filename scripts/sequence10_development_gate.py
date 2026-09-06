"""Sequence 10 forcing assembly evidence, separate from the inherited Sequence 9 freeze blocker."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from floodguard.common.integrity import verified_payload  # noqa: E402
from floodguard.common.release_evidence import lock_mismatches, source_fingerprint  # noqa: E402
from floodguard.forcing.contracts import Manifest, Product  # noqa: E402
from scripts.sequence9_development_gate import (  # noqa: E402
    command_ok,
    twin_readiness_blockers,
    validate_base_url,
)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def read(base: str, path: str, limit: int = 128 * 1024 * 1024) -> bytes:
    with urlopen(base + path, timeout=90) as response:
        payload = bytes(response.read(limit + 1))
    if len(payload) > limit:
        raise ValueError("forcing HTTP response exceeds limit")
    return payload


def product_evidence(base: str, fingerprint: str) -> list[dict[str, Any]]:
    result = []
    inventory = json.loads(read(base, "/forcing/products?city_id=kolkata", 4 * 1024 * 1024))
    if not isinstance(inventory, list):
        raise ValueError("forcing inventory is not a list")
    for item in inventory:
        product = Product.model_validate(item)
        prefix = f"/forcing/products/{product.forcing_package_id}/"
        payload = read(base, prefix + "manifest")
        verified_payload(
            payload,
            expected_sha256=product.manifest.sha256,
            expected_size=product.manifest.byte_size,
            max_bytes=128 * 1024 * 1024,
        )
        manifest = Manifest.model_validate_json(payload)
        if manifest.software_source_sha256 != fingerprint:
            continue
        for name, ref in manifest.artifacts.items():
            verified_payload(
                read(base, prefix + name),
                expected_sha256=ref.sha256,
                expected_size=ref.byte_size,
                max_bytes=128 * 1024 * 1024,
            )
        result.append(
            {
                "forcing_package_id": str(product.forcing_package_id),
                "http_artifacts_verified": 1 + len(manifest.artifacts),
                "manifest": manifest.model_dump(mode="json"),
            }
        )
    return result


def readiness_errors(readiness: dict[str, Any]) -> list[str]:
    errors = []
    for field in ("total_packages", "verified_packages", "eligible_packages"):
        value = readiness.get(field)
        if type(value) is not int or value < 1:
            errors.append(f"Forcing requires positive verified {field}.")
    if readiness.get("total_packages") != readiness.get("verified_packages"):
        errors.append("Forcing inventory contains unverified packages.")
    if readiness.get("integrity_failures") != []:
        errors.append("Forcing integrity failures are present or unknown.")
    if readiness.get("assembly_development_gate_passed") is not True:
        errors.append("Forcing assembly has not passed.")
    if (
        readiness.get("operational_validation_claimed") is not False
        or readiness.get("final_human_acceptance_pending") is not True
    ):
        errors.append("Forcing acceptance boundaries are not explicit.")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-checks", action="store_true")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts/validation/sequence10/development-gate.json",
    )
    args = parser.parse_args()
    base = validate_base_url(args.base_url)
    commit, fingerprint = git("rev-parse", "HEAD"), source_fingerprint(ROOT)
    errors = []
    if git("status", "--porcelain"):
        errors.append("Gate requires a clean committed checkout.")
    if sys.version_info[:2] != (3, 12) or lock_mismatches(ROOT / "requirements.lock"):
        errors.append("Pinned Python/dependency evidence failed.")
    software = False
    storage = False
    if args.run_checks and not errors:
        software = command_ok(
            [sys.executable, "scripts/verify.py", "--services", "--forcing-bootstrap"]
        )
        storage = command_ok(
            ["docker", "compose", "exec", "-T", "api", "python", "scripts/verify_storage.py"]
        )
    if not software:
        errors.append("Complete software/service/bootstrap verification has not passed.")
    if not storage:
        errors.append("Deployed conditional storage probe has not passed.")
    version, readiness, inherited, products = {}, {}, [], []
    try:
        version = json.loads(read(base, "/version"))
        if (
            version.get("sequence") != 10
            or version.get("version") != "1.0.0"
            or version.get("source_fingerprint") != fingerprint
            or version.get("dependency_lock_mismatches") != []
            or not str(version.get("runtime_python", "")).startswith("3.12.")
        ):
            errors.append("Deployed Sequence 10 source/runtime parity failed.")
        readiness = json.loads(read(base, "/forcing/readiness?city_id=kolkata"))
        errors.extend(readiness_errors(readiness))
        inherited = twin_readiness_blockers(
            json.loads(read(base, "/twins/readiness?city_id=kolkata"))
        )
        products = product_evidence(base, fingerprint)
        if not any(p["manifest"]["quality_summary"]["hydraulic_use_eligible"] for p in products):
            errors.append("No eligible forcing package matches this committed source.")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"Deployed evidence unavailable: {type(exc).__name__}")
    if git("rev-parse", "HEAD") != commit or git("status", "--porcelain"):
        errors.append("Repository changed during gate.")
    if source_fingerprint(ROOT) != fingerprint:
        errors.append("Source fingerprint changed during gate.")
    report = dict(
        sequence=10,
        release="1.0.0",
        created_at=datetime.now(UTC).isoformat(),
        repository_commit=commit,
        source_fingerprint=fingerprint,
        api_version=version,
        software_and_services_passed=software,
        deployed_conditional_storage_passed=storage,
        assembly_validation_status="PASSED" if not errors else "BLOCKED",
        assembly_blockers=errors,
        inherited_freeze_blockers=inherited,
        freeze_status="NOT_FROZEN" if errors or inherited else "ELIGIBLE_NOT_DECLARED",
        final_human_acceptance_pending=True,
        operational_validation_claimed=False,
        forcing_readiness=readiness,
        forcing_products=products,
        development_order_authorization="Owner requested Sequence 10 after the DATA-08-01 report.",
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if errors or inherited else 0


if __name__ == "__main__":
    raise SystemExit(main())
