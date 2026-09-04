"""Normalize the latest immutable Kolkata raw vector versions for Sequence 4."""

import argparse

from floodguard.harvester.contracts import DatasetVersionStatus
from floodguard.harvester.factory import build_harvester_service
from floodguard.registry.contracts import SourceCategory
from floodguard.registry.database import get_session_factory
from floodguard.registry.service import RegistryService
from floodguard.spatial.factory import build_spatial_service
from floodguard.spatial.service import CORE_KOLKATA_CATEGORIES, SpatialNormalizationError

OPTIONAL_VECTOR_CATEGORIES = {
    SourceCategory.DRAINAGE_MAP,
    SourceCategory.OPENSTREETMAP,
    SourceCategory.TRAFFIC,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize immutable raw Kolkata vector data into the metric spatial vault"
    )
    parser.add_argument("--city-id", default="kolkata")
    args = parser.parse_args()

    factory = get_session_factory()
    failures = 0
    processed = 0
    with factory() as session:
        registry = RegistryService(session)
        harvester = build_harvester_service(session)
        spatial = build_spatial_service(session)
        categories = CORE_KOLKATA_CATEGORIES | OPTIONAL_VECTOR_CATEGORIES
        sources = [
            source
            for source in registry.list_sources(city_id=args.city_id)
            if source.category in categories
        ]
        for source in sources:
            versions = harvester.list_source_versions(source.source_id)
            latest = next(
                (
                    version
                    for version in versions
                    if version.status is DatasetVersionStatus.COMPLETE
                ),
                None,
            )
            if latest is None:
                print(f"SKIPPED {source.dataset_name}: no COMPLETE raw version")
                continue
            try:
                result = spatial.normalize_dataset(source, latest)
            except SpatialNormalizationError as exc:
                failures += 1
                print(f"FAILED {source.dataset_name}: {exc}")
                continue
            processed += 1
            print(
                f"NORMALIZED {source.dataset_name}: created={result.created_layers} "
                f"reused={result.reused_layers} skipped={result.skipped_objects}"
            )

        readiness = spatial.readiness(city_id=args.city_id)
        print(
            f"spatial readiness: layers={readiness.normalized_layers} "
            f"categories={','.join(readiness.normalized_categories)} "
            f"max_roundtrip_error_m={readiness.max_roundtrip_error_m}"
        )
        if readiness.missing_core_categories:
            failures += 1
            print(
                "FAILED missing core categories: "
                + ", ".join(readiness.missing_core_categories)
            )
        if not readiness.alignment_check_passed:
            failures += 1
            print("FAILED metric alignment check")
        if not readiness.vertical_metadata_valid:
            failures += 1
            print("FAILED vertical-reference metadata check")
        if not readiness.rainfall_conservation.passed:
            failures += 1
            print("FAILED rainfall conservation check")

    if processed == 0:
        raise SystemExit("No harvested Kolkata vector sources were available for normalization")
    if failures:
        raise SystemExit(f"Kolkata spatial bootstrap completed with {failures} failure(s)")
    print("Kolkata spatial bootstrap completed successfully")


if __name__ == "__main__":
    main()
