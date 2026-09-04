"""Local verification entry point through Sequence 4."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SERVICES = {"postgres", "redis", "nats", "minio", "traefik", "api"}
HEALTHCHECKED_SERVICES = EXPECTED_SERVICES


def run(command: list[str]) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def verify_python() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(
            f"FloodGuard-AI requires Python 3.12.x; found {sys.version.split()[0]}"
        )
    print(f"OK Python {sys.version.split()[0]}")


def verify_files() -> None:
    required = [
        ROOT / "requirements.lock",
        ROOT / "docker-compose.yml",
        ROOT / ".env.example",
        ROOT / ".gitignore",
        ROOT / "agent.md",
        ROOT / "alembic.ini",
        ROOT / "migrations" / "versions" / "0001_sequence_2_registry.py",
        ROOT / "migrations" / "versions" / "0002_sequence_3_harvester.py",
        ROOT / "migrations" / "versions" / "0003_sequence_4_spatial.py",
        ROOT / "floodguard" / "registry" / "contracts.py",
        ROOT / "floodguard" / "registry" / "seed.py",
        ROOT / "floodguard" / "harvester" / "contracts.py",
        ROOT / "floodguard" / "harvester" / "service.py",
        ROOT / "floodguard" / "harvester" / "vault.py",
        ROOT / "floodguard" / "harvester" / "bootstrap.py",
        ROOT / "floodguard" / "spatial" / "contracts.py",
        ROOT / "floodguard" / "spatial" / "reference.py",
        ROOT / "floodguard" / "spatial" / "resampling.py",
        ROOT / "floodguard" / "spatial" / "service.py",
        ROOT / "floodguard" / "spatial" / "bootstrap.py",
        ROOT / "docs" / "architecture" / "sequence-04-spatial-normalization.md",
        ROOT / "docs" / "Urban_Flood_Digital_Twin_Authoritative_20_Sequence_Plan_FROZEN.md",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"Missing required files: {', '.join(missing)}")
    print("OK required repository files")


def verify_static_and_tests() -> None:
    run([sys.executable, "-m", "ruff", "check", "."])
    run([sys.executable, "-m", "mypy", "floodguard", "apps", "scripts"])
    run([sys.executable, "-m", "pytest"])


def docker_service_id(service: str) -> str:
    result = subprocess.run(
        ["docker", "compose", "ps", "-q", service],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def get_json(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=5) as response:
        raw_payload: object = json.loads(response.read())
    if not isinstance(raw_payload, dict):
        raise SystemExit(f"Expected JSON object from {url}")
    payload: dict[str, object] = {}
    for key, value in raw_payload.items():
        if not isinstance(key, str):
            raise SystemExit(f"Expected string JSON object keys from {url}")
        payload[key] = value
    return payload


def get_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as response:
        raw_body: object = response.read()
    if not isinstance(raw_body, bytes):
        raise SystemExit(f"Expected byte response body from {url}")
    return raw_body.decode("utf-8")


def verify_services() -> None:
    run(["docker", "compose", "config", "--quiet"])
    for service in sorted(EXPECTED_SERVICES):
        container_id = docker_service_id(service)
        if not container_id:
            raise SystemExit(f"Service {service} is not running")
        if service in HEALTHCHECKED_SERVICES:
            result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
                    container_id,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            status = result.stdout.strip()
            if status != "healthy":
                raise SystemExit(f"Service {service} health is {status!r}, expected 'healthy'")
        print(f"OK service {service}")

    if get_json("http://localhost:8000/health").get("status") != "ok":
        raise SystemExit("API health response is not ok")
    print("OK API /health")

    version = get_json("http://localhost:8000/version")
    if version.get("sequence") != 4 or version.get("version") != "0.4.0":
        raise SystemExit("API is not serving FloodGuard-AI Sequence 4 / v0.4.0")
    print("OK API /version")

    registry = get_json("http://localhost:8000/registry/readiness")
    if registry.get("catalogue_complete") is not True:
        raise SystemExit("Sequence 2 registry catalogue is incomplete")
    total_sources = registry.get("total_sources")
    if not isinstance(total_sources, int) or total_sources < 17:
        raise SystemExit("Sequence 2 registry source catalogue was not seeded")
    print("OK API /registry/readiness")

    harvester = get_json("http://localhost:8000/harvester/readiness")
    permitted = harvester.get("automation_permitted_sources")
    if not isinstance(permitted, int) or permitted < 1:
        raise SystemExit("Sequence 3 has no automation-permitted source catalogue")
    if harvester.get("raw_bucket") != "floodguard-raw":
        raise SystemExit("Sequence 3 raw bucket configuration is unexpected")
    print("OK API /harvester/readiness")

    spatial = get_json("http://localhost:8000/spatial/readiness")
    if spatial.get("working_crs") != "EPSG:32645":
        raise SystemExit("Sequence 4 working CRS configuration is unexpected")
    rainfall = spatial.get("rainfall_conservation")
    if not isinstance(rainfall, dict) or rainfall.get("passed") is not True:
        raise SystemExit("Sequence 4 rainfall conservation self-check failed")
    if spatial.get("spatial_bucket") != "floodguard-spatial":
        raise SystemExit("Sequence 4 spatial bucket configuration is unexpected")
    print("OK API /spatial/readiness")

    if "MapLibre" not in get_text("http://localhost:8000/spatial/qa"):
        raise SystemExit("Sequence 4 QA viewer is not reachable")
    print("OK API /spatial/qa")


def run_harvester_bootstrap_gate() -> None:
    run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "api",
            "python",
            "-m",
            "floodguard.harvester.bootstrap",
            "--city-id",
            "kolkata",
        ]
    )
    readiness = get_json("http://localhost:8000/harvester/readiness")
    harvested = readiness.get("harvested_sources")
    if not isinstance(harvested, int) or harvested < 1:
        raise SystemExit("Sequence 3 bootstrap did not create any immutable raw dataset version")
    print("OK Kolkata immutable raw-data bootstrap gate")


def run_spatial_bootstrap_gate() -> None:
    run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "api",
            "python",
            "-m",
            "floodguard.spatial.bootstrap",
            "--city-id",
            "kolkata",
        ]
    )
    readiness = get_json("http://localhost:8000/spatial/readiness")
    normalized_layers = readiness.get("normalized_layers")
    if not isinstance(normalized_layers, int) or normalized_layers < 3:
        raise SystemExit("Sequence 4 bootstrap did not create the three core normalized layers")
    missing = readiness.get("missing_core_categories")
    if not isinstance(missing, list) or missing:
        raise SystemExit(f"Sequence 4 core normalized categories are incomplete: {missing}")
    if readiness.get("alignment_check_passed") is not True:
        raise SystemExit("Sequence 4 metric alignment gate failed")
    if readiness.get("vertical_metadata_valid") is not True:
        raise SystemExit("Sequence 4 vertical-reference gate failed")
    rainfall = readiness.get("rainfall_conservation")
    if not isinstance(rainfall, dict) or rainfall.get("passed") is not True:
        raise SystemExit("Sequence 4 rainfall conservation gate failed")
    if "FloodGuard-AI · Spatial QA" not in get_text("http://localhost:8000/spatial/qa"):
        raise SystemExit("Sequence 4 MapLibre QA viewer gate failed")
    print("OK Kolkata spatial normalization and QA completion gate")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--services",
        action="store_true",
        help="also verify the running Docker Compose platform and Sequence 4 APIs",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="run the networked Sequence 3 Kolkata raw-data gate; implies --services",
    )
    parser.add_argument(
        "--spatial-bootstrap",
        action="store_true",
        help="run the Sequence 4 Kolkata spatial completion gate; implies --services",
    )
    args = parser.parse_args()

    verify_python()
    verify_files()
    verify_static_and_tests()
    if args.services or args.bootstrap or args.spatial_bootstrap:
        verify_services()
    if args.bootstrap:
        run_harvester_bootstrap_gate()
    if args.spatial_bootstrap:
        run_spatial_bootstrap_gate()
    print("Sequence 4 verification PASSED")


if __name__ == "__main__":
    main()
