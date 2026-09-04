"""One-shot Kolkata bootstrap worker for Sequence 3.

Run inside the application container so PostgreSQL and MinIO service names resolve:

    docker compose exec api python -m floodguard.harvester.bootstrap --city-id kolkata
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from uuid import UUID

from floodguard.harvester.acquisition import AcquisitionError
from floodguard.harvester.factory import build_harvester_service
from floodguard.harvester.service import HarvestAccessError, HarvestConflictError
from floodguard.registry.contracts import AccessMethod, SourceRead
from floodguard.registry.database import get_session_factory
from floodguard.registry.service import RegistryService


SAFE_DEFAULT_METHODS = {
    AccessMethod.CKAN,
    AccessMethod.HTTP,
    AccessMethod.REST,
}


def _selected_sources(
    sources: Iterable[SourceRead],
    *,
    requested_ids: set[UUID],
    include_pbf: bool,
    overpass_query: str | None,
) -> list[tuple[SourceRead, dict[str, object]]]:
    selected: list[tuple[SourceRead, dict[str, object]]] = []
    for source in sources:
        if requested_ids and source.source_id not in requested_ids:
            continue
        parameters: dict[str, object] = {}
        if source.access_method in SAFE_DEFAULT_METHODS:
            selected.append((source, parameters))
        elif source.access_method is AccessMethod.PBF_EXTRACT and include_pbf:
            selected.append((source, parameters))
        elif source.access_method is AccessMethod.OVERPASS and overpass_query:
            parameters["query"] = overpass_query
            selected.append((source, parameters))
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Harvest governed raw data into the immutable vault")
    parser.add_argument("--city-id", default="kolkata")
    parser.add_argument("--source-id", action="append", default=[])
    parser.add_argument(
        "--include-authorized",
        action="store_true",
        help="allow authorization-required sources when credentials and adapters are configured",
    )
    parser.add_argument(
        "--include-pbf",
        action="store_true",
        help="allow large PBF extract downloads; disabled by default to protect bandwidth",
    )
    parser.add_argument(
        "--overpass-query",
        help="explicit bounded Overpass query; no unbounded query is invented by the bootstrap job",
    )
    args = parser.parse_args()
    requested_ids = {UUID(value) for value in args.source_id}

    factory = get_session_factory()
    failures = 0
    with factory() as session:
        registry = RegistryService(session)
        harvester = build_harvester_service(session)
        sources = registry.list_sources(city_id=args.city_id)
        selected = _selected_sources(
            sources,
            requested_ids=requested_ids,
            include_pbf=args.include_pbf,
            overpass_query=args.overpass_query,
        )
        if not selected:
            raise SystemExit("No sources matched the bootstrap selection")

        for source, parameters in selected:
            try:
                result = harvester.harvest_source(
                    source,
                    parameters=parameters,
                    include_authorized=args.include_authorized,
                )
            except (AcquisitionError, HarvestAccessError, HarvestConflictError, RuntimeError) as exc:
                failures += 1
                print(f"FAILED {source.dataset_name}: {exc}")
            else:
                print(
                    f"{result.disposition.value} {source.dataset_name}: "
                    f"version={result.dataset_version_id} objects={result.object_count} "
                    f"bytes={result.total_bytes}"
                )

    if failures:
        raise SystemExit(f"Kolkata bootstrap completed with {failures} failure(s)")
    print("Kolkata bootstrap completed successfully")


if __name__ == "__main__":
    main()
