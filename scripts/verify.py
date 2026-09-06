"""Local verification entry point through Sequence 9."""

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
        raise SystemExit(f"FloodGuard-AI requires Python 3.12.x; found {sys.version.split()[0]}")
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
        ROOT / "migrations" / "versions" / "0004_sequence_5_reconstruction.py",
        ROOT / "migrations" / "versions" / "0005_sequence_6_terrain.py",
        ROOT / "migrations" / "versions" / "0006_sequence_7_urban_gis.py",
        ROOT / "migrations" / "versions" / "0007_sequence_8_drain_model.py",
        ROOT / "migrations" / "versions" / "0008_sequence_9_twin.py",
        ROOT / "floodguard" / "twin" / "service.py",
        ROOT / "floodguard" / "drainage" / "service.py",
        ROOT / "floodguard" / "drainage" / "qa_viewer.py",
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
        ROOT / "floodguard" / "reconstruction" / "contracts.py",
        ROOT / "floodguard" / "reconstruction" / "pdf_native.py",
        ROOT / "floodguard" / "reconstruction" / "service.py",
        ROOT / "floodguard" / "reconstruction" / "bootstrap.py",
        ROOT / "floodguard" / "terrain" / "contracts.py",
        ROOT / "floodguard" / "terrain" / "conditioning.py",
        ROOT / "floodguard" / "terrain" / "service.py",
        ROOT / "floodguard" / "terrain" / "bootstrap.py",
        ROOT / "floodguard" / "terrain" / "qa_viewer.py",
        ROOT / "floodguard" / "terrain" / "acquisition.py",
        ROOT / "floodguard" / "terrain" / "acquire_srtm.py",
        ROOT / "floodguard" / "terrain" / "jobs.py",
        ROOT / "floodguard" / "urban_gis" / "contracts.py",
        ROOT / "floodguard" / "urban_gis" / "policy.py",
        ROOT / "floodguard" / "urban_gis" / "service.py",
        ROOT / "floodguard" / "urban_gis" / "bootstrap.py",
        ROOT / "floodguard" / "urban_gis" / "qa_viewer.py",
        ROOT / "floodguard" / "reconstruction" / "calibrations" / "kmc-opencity-ward-7-v1.json",
        ROOT / "docs" / "architecture" / "sequence-05-drainage-reconstruction.md",
        ROOT / "docs" / "architecture" / "sequence-06-terrain-conditioning.md",
        ROOT / "docs" / "architecture" / "sequence-07-urban-gis.md",
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
    if version.get("sequence") != 9 or version.get("version") != "0.9.0":
        raise SystemExit("API is not serving FloodGuard-AI Sequence 9 / v0.9.0")
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

    reconstruction = get_json("http://localhost:8000/reconstruction/readiness")
    if "completion_gate_passed" not in reconstruction:
        raise SystemExit("Sequence 5 reconstruction readiness contract is incomplete")
    if "Drainage Reconstruction QA" not in get_text("http://localhost:8000/reconstruction/qa"):
        raise SystemExit("Sequence 5 reconstruction QA viewer is not reachable")
    print("OK API /reconstruction/readiness and /reconstruction/qa")

    terrain = get_json("http://localhost:8000/terrain/readiness")
    if "completion_gate_passed" not in terrain:
        raise SystemExit("Sequence 6 terrain readiness contract is incomplete")
    if terrain.get("qa_viewer_path") != "/terrain/qa":
        raise SystemExit("Sequence 6 terrain QA path is unexpected")
    terrain_qa = get_text("http://localhost:8000/terrain/qa")
    if "Terrain QA" not in terrain_qa:
        raise SystemExit("Sequence 6 terrain QA viewer is not reachable")
    if "Acquire pilot terrain" not in terrain_qa:
        raise SystemExit("Sequence 6 automatic terrain acquisition is missing; rebuild the API")
    print("OK API /terrain/readiness and /terrain/qa")

    urban_gis = get_json("http://localhost:8000/urban-gis/readiness?city_id=kolkata")
    if urban_gis.get("current_pipeline_version") != "sequence-7-urban-gis-v1":
        raise SystemExit("Sequence 7 urban GIS pipeline identity is unexpected")
    if "technical_development_gate_passed" not in urban_gis:
        raise SystemExit("Sequence 7 urban GIS readiness contract is incomplete")
    if urban_gis.get("qa_viewer_path") != "/urban-gis/qa":
        raise SystemExit("Sequence 7 urban GIS QA path is unexpected")
    if "Urban GIS QA" not in get_text("http://localhost:8000/urban-gis/qa"):
        raise SystemExit("Sequence 7 urban GIS QA viewer is not reachable")
    print("OK API /urban-gis/readiness and /urban-gis/qa")


def verify_drainage() -> None:
    readiness = get_json("http://localhost:8000/drainage/readiness?city_id=kolkata")
    if readiness.get("current_pipeline_version") != "sequence-8-drain-model-v1":
        raise SystemExit("Sequence 8 drain pipeline identity mismatch")
    if "Drain Model QA" not in get_text("http://localhost:8000/drainage/qa"):
        raise SystemExit("Sequence 8 drain QA viewer unavailable")
    print("OK API /drainage/readiness and /drainage/qa")


def verify_twins() -> None:
    readiness = get_json("http://localhost:8000/twins/readiness?city_id=kolkata")
    if readiness.get("current_pipeline_version") != "sequence-9-twin-v1":
        raise SystemExit("Sequence 9 twin pipeline identity mismatch")
    if "Twin Manifest QA" not in get_text("http://localhost:8000/twins/qa"):
        raise SystemExit("Sequence 9 twin QA viewer unavailable")
    print("OK API /twins/readiness and /twins/qa")


def run_twin_bootstrap_gate() -> None:
    run(["docker", "compose", "exec", "-T", "api", "python", "-m", "floodguard.twin.bootstrap"])
    readiness = get_json("http://localhost:8000/twins/readiness?city_id=kolkata")
    if readiness.get("assembly_development_gate_passed") is not True:
        raise SystemExit("Sequence 9 twin assembly/recreation gate failed")
    print("OK Sequence 9 assembly/recreation; real cross-ward freeze gate remains separate")


def run_drainage_bootstrap_gate() -> None:
    run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "api",
            "python",
            "-m",
            "floodguard.drainage.bootstrap",
            "--city-id",
            "kolkata",
        ]
    )
    readiness = get_json("http://localhost:8000/drainage/readiness?city_id=kolkata")
    if readiness.get("technical_development_gate_passed") is not True:
        raise SystemExit("Sequence 8 automated drain development gate failed")
    print("OK Sequence 8 reference model and existing real-source import gate")


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


def run_reconstruction_bootstrap_gate() -> None:
    run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "api",
            "python",
            "-m",
            "floodguard.reconstruction.bootstrap",
            "--city-id",
            "kolkata",
        ]
    )
    readiness = get_json("http://localhost:8000/reconstruction/readiness")
    minimum_counts = {
        "total_drains": 100,
        "total_structures": 80,
        "total_labels": 90,
    }
    for field, minimum in minimum_counts.items():
        value = readiness.get(field)
        if not isinstance(value, int) or value < minimum:
            raise SystemExit(
                f"Sequence 5 {field}={value!r} is below the pinned Ward 7 minimum {minimum}"
            )
    geographic = readiness.get("geographically_valid")
    if not isinstance(geographic, int) or geographic < 1:
        raise SystemExit("Sequence 5 has no reconstruction within its georeference tolerance")
    native = readiness.get("native_vector_text_reconstructions")
    if not isinstance(native, int) or native < 1:
        raise SystemExit("Sequence 5 did not preserve native vector/text extraction")
    if readiness.get("completion_gate_passed") is not True:
        reason = readiness.get("completion_gate_reason")
        raise SystemExit(f"Sequence 5 human-review completion gate is not passed: {reason}")
    if "Drainage Reconstruction QA" not in get_text("http://localhost:8000/reconstruction/qa"):
        raise SystemExit("Sequence 5 MapLibre reconstruction QA viewer gate failed")
    print("OK real KMC drainage reconstruction and human-review completion gate")


def run_terrain_bootstrap_gate() -> None:
    run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "api",
            "python",
            "-m",
            "floodguard.terrain.bootstrap",
            "--city-id",
            "kolkata",
        ]
    )
    readiness = get_json("http://localhost:8000/terrain/readiness")
    if readiness.get("completion_gate_passed") is not True:
        reason = readiness.get("completion_gate_reason")
        raise SystemExit(f"Sequence 6 terrain completion gate is not passed: {reason}")
    if readiness.get("best_readiness_status") not in {
        "HYDRAULIC_SCENARIO_READY",
        "HYDRAULIC_VALIDATED",
    }:
        raise SystemExit("Sequence 6 terrain readiness is not hydraulically usable")
    if "Terrain QA" not in get_text("http://localhost:8000/terrain/qa"):
        raise SystemExit("Sequence 6 terrain MapLibre QA viewer gate failed")
    print("OK terrain conditioning and conservative readiness completion gate")


def run_urban_gis_bootstrap_gate() -> None:
    run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "api",
            "python",
            "-m",
            "floodguard.urban_gis.bootstrap",
            "--city-id",
            "kolkata",
        ]
    )
    readiness = get_json("http://localhost:8000/urban-gis/readiness?city_id=kolkata")
    if readiness.get("technical_development_gate_passed") is not True:
        raise SystemExit("Sequence 7 automated urban GIS development gate did not pass")
    ready_total = 0
    for field in ("reference_ready", "provisional_real_ready", "reviewed_real_ready"):
        value = readiness.get(field)
        if not isinstance(value, int):
            raise SystemExit(f"Sequence 7 readiness field {field} is invalid")
        ready_total += value
    if ready_total < 1:
        raise SystemExit("Sequence 7 bootstrap produced no ready current-pipeline package")
    if "Urban GIS QA" not in get_text("http://localhost:8000/urban-gis/qa"):
        raise SystemExit("Sequence 7 urban GIS QA viewer gate failed")
    print("OK Sequence 7 automated urban GIS development gate")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--services",
        action="store_true",
        help="also verify the running Docker Compose platform and APIs through Sequence 9",
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
    parser.add_argument(
        "--reconstruction-bootstrap",
        action="store_true",
        help=(
            "run the Sequence 5 real KMC map gate; requires a prior recorded human QA "
            "approval and implies --services"
        ),
    )
    parser.add_argument(
        "--terrain-bootstrap",
        action="store_true",
        help=(
            "run the Sequence 6 final terrain completion gate; requires assessed real terrain "
            "and implies --services"
        ),
    )
    parser.add_argument(
        "--urban-gis-bootstrap",
        action="store_true",
        help=(
            "run the Sequence 7 automated reference-package development gate; final real-pilot "
            "human acceptance remains deferred to Sequence 20"
        ),
    )
    parser.add_argument(
        "--drainage-bootstrap",
        action="store_true",
        help="build drain reference and import existing real pilot; no acquisition",
    )
    parser.add_argument(
        "--twin-bootstrap",
        action="store_true",
        help="build and recreate reference and exact provisional pilot twins",
    )
    args = parser.parse_args()

    verify_python()
    verify_files()
    verify_static_and_tests()
    if (
        args.services
        or args.bootstrap
        or args.spatial_bootstrap
        or args.reconstruction_bootstrap
        or args.terrain_bootstrap
        or args.urban_gis_bootstrap
        or args.drainage_bootstrap
        or args.twin_bootstrap
    ):
        verify_services()
        verify_drainage()
        verify_twins()
    if args.bootstrap:
        run_harvester_bootstrap_gate()
    if args.spatial_bootstrap:
        run_spatial_bootstrap_gate()
    if args.reconstruction_bootstrap:
        run_reconstruction_bootstrap_gate()
    if args.terrain_bootstrap:
        run_terrain_bootstrap_gate()
    if args.urban_gis_bootstrap:
        run_urban_gis_bootstrap_gate()

    if args.drainage_bootstrap:
        run_drainage_bootstrap_gate()

    if args.twin_bootstrap:
        run_twin_bootstrap_gate()

    print("Software verification through Sequence 9 PASSED")
    if args.twin_bootstrap:
        print("Sequence 9 twin assembly software gate PASSED")
        print("Sequence freeze also requires the genuine real cross-ward gate.")
    elif args.drainage_bootstrap:
        print("Sequence 8 automated development gate PASSED")
        print("Real cross-ward evidence and final human acceptance remain explicit constraints.")
    elif args.urban_gis_bootstrap:
        print("Sequence 7 automated development gate PASSED")
        print("Final real-pilot human acceptance remains deferred to Sequence 20.")
    else:
        print("Twin bootstrap was not checked; run --twin-bootstrap for assembly verification.")


if __name__ == "__main__":
    main()
