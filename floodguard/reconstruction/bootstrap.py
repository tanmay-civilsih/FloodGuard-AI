"""Reconstruct the calibrated real KMC Ward 7 drainage map from the immutable raw vault."""

import argparse

from floodguard.harvester.contracts import DatasetVersionStatus
from floodguard.harvester.factory import build_harvester_service
from floodguard.reconstruction.calibration import load_calibrations
from floodguard.reconstruction.factory import build_reconstruction_service
from floodguard.registry.contracts import SourceCategory
from floodguard.registry.database import get_session_factory
from floodguard.registry.service import RegistryService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconstruct a calibrated real KMC drainage drawing"
    )
    parser.add_argument("--city-id", default="kolkata")
    args = parser.parse_args()

    calibrations = load_calibrations()
    if not calibrations:
        raise SystemExit("No versioned drainage-map calibrations are available")

    factory = get_session_factory()
    processed = 0
    with factory() as session:
        registry = RegistryService(session)
        harvester = build_harvester_service(session)
        reconstruction = build_reconstruction_service(session)
        sources = [
            source
            for source in registry.list_sources(city_id=args.city_id)
            if source.category is SourceCategory.DRAINAGE_MAP
        ]
        for source in sources:
            version = next(
                (
                    item
                    for item in harvester.list_source_versions(source.source_id)
                    if item.status is DatasetVersionStatus.COMPLETE
                ),
                None,
            )
            if version is None:
                continue
            for calibration in calibrations:
                raw_object = next(
                    (
                        item
                        for item in version.objects
                        if item.filename == calibration.source_filename
                        and item.sha256 == calibration.source_sha256
                    ),
                    None,
                )
                if raw_object is None:
                    continue
                result = reconstruction.reconstruct(
                    source,
                    version,
                    raw_object,
                    calibration,
                )
                processed += 1
                print(
                    f"RECONSTRUCTED ward={calibration.ward_id} "
                    f"id={result.reconstruction_id} created={result.created} "
                    f"drains={result.drain_count} structures={result.structure_count} "
                    f"labels={result.label_count} rmse_m={result.georeference_rmse_m:.3f} "
                    f"status={result.status.value}"
                )

        readiness = reconstruction.readiness(city_id=args.city_id)
        print(
            f"reconstruction readiness: total={readiness.total_reconstructions} "
            f"approved={readiness.approved_reconstructions} "
            f"pending={readiness.pending_review} "
            f"gate={readiness.completion_gate_passed}"
        )
        print(readiness.completion_gate_reason)
    if processed == 0:
        raise SystemExit(
            "No calibrated immutable KMC drainage object matched; rerun the Sequence 3 "
            "harvester and inspect source hashes"
        )


if __name__ == "__main__":
    main()

