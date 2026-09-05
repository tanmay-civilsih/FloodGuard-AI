"""Import a legitimately downloaded SRTMGL1 HGT file for an approved pilot extent."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from floodguard.common.config import get_settings
from floodguard.harvester.factory import build_harvester_service
from floodguard.harvester.repository import HarvesterRepository
from floodguard.reconstruction.contracts import DrainageReconstructionRead, ReconstructionStatus
from floodguard.reconstruction.repository import ReconstructionRepository
from floodguard.registry.database import get_session_factory
from floodguard.registry.seed import seed_id
from floodguard.registry.service import RegistryService
from floodguard.terrain.factory import build_terrain_service
from floodguard.terrain.importer import SrtmImportRequest, TerrainInputImporter
from floodguard.terrain.srtm import SRTM_BYTES, SrtmTarget


def select_pilot(
    records: list[DrainageReconstructionRead], city_id: str, ward_id: str, working_crs: str
) -> DrainageReconstructionRead:
    candidates = [item for item in records if item.city_id == city_id and item.ward_id == ward_id]
    if not candidates:
        raise ValueError("no reconstruction exists for this pilot ward")
    latest = max(candidates, key=lambda item: (item.created_at, str(item.reconstruction_id)))
    if latest.status is not ReconstructionStatus.APPROVED:
        raise ValueError("the latest pilot reconstruction requires recorded human QA approval")
    if latest.working_crs != working_crs:
        raise ValueError("pilot reconstruction does not use the configured working CRS")
    return latest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city-id", default="kolkata")
    parser.add_argument("--ward-id", default="7")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--imported-by")
    parser.add_argument(
        "--access-reference", help="actual download source/access basis; never a token"
    )
    parser.add_argument("--cell-size-m", type=float, default=30.0)
    parser.add_argument(
        "--plan", action="store_true", help="show input requirements without writing"
    )
    parser.add_argument("--dry-run", action="store_true", help="validate the file without writing")
    args = parser.parse_args()
    if not args.plan and (args.file is None or not args.imported_by or not args.access_reference):
        parser.error("import requires --file, --imported-by and --access-reference (or use --plan)")
    settings = get_settings()
    try:
        with get_session_factory()() as session:
            source = RegistryService(session).get_source(seed_id("nasa-srtmgl1"))
            if source.city_id != args.city_id:
                raise ValueError("the registered SRTM source does not belong to this city")
            repository = ReconstructionRepository(session)
            pilot = select_pilot(
                repository.reads(repository.list_reconstructions(city_id=args.city_id)),
                args.city_id,
                args.ward_id,
                settings.working_crs,
            )
            target = SrtmTarget(
                working_crs=settings.working_crs,
                bounds_working=pilot.bounds_working,
                cell_size_m=args.cell_size_m,
            )
            if args.plan:
                west, south, east, north = pilot.bounds_wgs84
                tiles = [
                    f"{('N' if lat >= 0 else 'S')}{abs(lat):02d}"
                    f"{('E' if lon >= 0 else 'W')}{abs(lon):03d}.hgt"
                    for lat in range(math.floor(south), math.floor(north) + 1)
                    for lon in range(math.floor(west), math.floor(east) + 1)
                ]
                print(
                    json.dumps(
                        {
                            "source_reference": source.endpoint,
                            "source_id": str(source.source_id),
                            "source_access_class": source.access_class.value,
                            "source_status": source.status.value,
                            "pilot_reconstruction_id": str(pilot.reconstruction_id),
                            "target": target.model_dump(mode="json"),
                            "required_tiles": tiles,
                            "supported": len(tiles) == 1,
                            "expected_hgt_bytes": SRTM_BYTES,
                            "initial_readiness": "VISUAL_READY",
                            "writes_performed": False,
                        },
                        indent=2,
                    )
                )
                return
            if args.file.stat().st_size != SRTM_BYTES:
                raise ValueError(f"expected an uncompressed SRTMGL1 HGT of {SRTM_BYTES} bytes")
            with args.file.open("rb") as handle:
                payload = handle.read(SRTM_BYTES + 1)
            request = SrtmImportRequest(
                filename=args.file.name,
                target=target,
                pilot_area_id=f"{args.city_id}-ward-{args.ward_id}",
                boundary_reference=(
                    f"reconstruction://{pilot.reconstruction_id}"
                    f"#working_sha256={pilot.working_sha256}"
                ),
                imported_by=args.imported_by,
                access_reference=args.access_reference,
            )
            importer = TerrainInputImporter(
                HarvesterRepository(session),
                build_harvester_service(session).vault,
                build_terrain_service(session),
                max_total_bytes=settings.harvest_max_total_bytes,
                max_object_bytes=settings.harvest_max_object_bytes,
            )
            result = importer.import_srtm(source, payload, request, dry_run=args.dry_run)
            print(result.model_dump_json(indent=2))
            print("Terrain assessments and local vertical-reference compatibility remain pending.")
    except (OSError, RuntimeError, ValueError, LookupError) as exc:
        raise SystemExit(f"Terrain import failed: {exc}") from exc


if __name__ == "__main__":
    main()
