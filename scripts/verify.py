"""Local verification entry point for Sequence 1."""

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
            f"FloodGuard-AI Sequence 1 requires Python 3.12.x; found {sys.version.split()[0]}"
        )
    print(f"OK Python {sys.version.split()[0]}")


def verify_files() -> None:
    required = [
        ROOT / "requirements.lock",
        ROOT / "docker-compose.yml",
        ROOT / ".env.example",
        ROOT / ".gitignore",
        ROOT / "agent.md",
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

    with urllib.request.urlopen("http://localhost:8000/health", timeout=5) as response:
        payload = json.loads(response.read())
    if payload.get("status") != "ok":
        raise SystemExit("API health response is not ok")
    print("OK API /health")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--services",
        action="store_true",
        help="also verify the running Docker Compose platform and API",
    )
    args = parser.parse_args()

    verify_python()
    verify_files()
    verify_static_and_tests()
    if args.services:
        verify_services()
    print("Sequence 1 verification PASSED")


if __name__ == "__main__":
    main()
