"""Build Sequence 6 products from a versioned immutable terrain package.

The worker intentionally accepts only an explicit ``*.terrain.json`` package.  It does not
download, invent, or infer elevation data from a generic source object.

Run inside the application container::

    docker compose exec api python -m floodguard.terrain.bootstrap --city-id kolkata
"""

from __future__ import annotations

import argparse
import uuid

from floodguard.harvester.contracts import DatasetVersionRead, DatasetVersionStatus, RawObjectRead
from floodguard.harvester.repository import HarvesterRepository
from floodguard.registry.contracts import SourceCategory
from floodguard.registry.database import get_session_factory
from floodguard.registry.service import RegistryService
from floodguard.terrain.factory import build_terrain_service
from floodguard.terrain.service import TerrainConditioningError


def _terrain_objects(version: DatasetVersionRead) -> list[RawObjectRead]:
    accepted_suffixes = (".terrain.json", ".terrain-package.json")
    return [
        item
        for item in version.objects
        if item.filename.lower().endswith(accepted_suffixes)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build immutable visual and hydraulic terrain products"
    )
    parser.add_argument("--city-id", default="kolkata")
    parser.add_argument("--source-id", action="append", default=[])
    args = parser.parse_args()
    requested_ids = {uuid.UUID(value) for value in args.source_id}

    factory = get_session_factory()
    failures = 0
    built = 0
    with factory() as session:
        registry = RegistryService(session)
        harvester = HarvesterRepository(session)
        terrain = build_terrain_service(session)
        sources = registry.list_sources(city_id=args.city_id, category=SourceCategory.ELEVATION)
        if requested_ids:
            sources = [source for source in sources if source.source_id in requested_ids]
        if not sources:
            raise SystemExit("No ELEVATION registry source matched the bootstrap selection")

        for source in sources:
            version_record = harvester.latest_complete(source.source_id)
            if version_record is None:
                print(f"SKIPPED {source.dataset_name}: no COMPLETE immutable version")
                continue
            version = DatasetVersionRead.model_validate(version_record)
            if version.status is not DatasetVersionStatus.COMPLETE:
                print(f"SKIPPED {source.dataset_name}: latest version is not COMPLETE")
                continue
            packages = _terrain_objects(version)
            if not packages:
                print(
                    f"SKIPPED {source.dataset_name}: no *.terrain.json package in "
                    "the latest immutable version; no DEM was invented"
                )
                continue
            for raw_object in packages:
                try:
                    result = terrain.build_from_raw(source, version, raw_object)
                except (TerrainConditioningError, RuntimeError, ValueError) as exc:
                    failures += 1
                    print(f"FAILED {source.dataset_name}/{raw_object.filename}: {exc}")
                else:
                    built += 1
                    print(
                        f"{('BUILT' if result.created else 'REUSED')} terrain="
                        f"{result.terrain_id} readiness={result.readiness_status.value} "
                        f"cells={result.width}x{result.height} "
                        f"preserved_depressions={result.preserved_depression_count} "
                        f"multi_level_structures={result.multi_level_structure_count}"
                    )

    if failures:
        raise SystemExit(f"Terrain bootstrap completed with {failures} failure(s)")
    if not built:
        raise SystemExit(
            "No versioned terrain package is available. For a downloaded SRTMGL1 HGT, run "
            "python -m floodguard.terrain.import_srtm --plan inside the API container. "
            "A registry portal entry alone does not acquire or convert elevation data."
        )
    else:
        print(f"Terrain bootstrap completed successfully: {built} package(s)")


if __name__ == "__main__":
    main()
