"""Build the deterministic Sequence 7 reference package for automated development validation."""

from __future__ import annotations

import argparse
import json

from floodguard.common.config import get_settings
from floodguard.registry.database import get_session_factory
from floodguard.urban_gis.factory import build_urban_gis_service
from floodguard.urban_gis.reference import reference_package


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city-id", default="kolkata")
    parser.add_argument("--pilot-area-id", default="kolkata-sequence7-reference")
    args = parser.parse_args()

    settings = get_settings()
    with get_session_factory()() as session:
        service = build_urban_gis_service(session)
        result = service.build(
            reference_package(
                city_id=args.city_id,
                pilot_area_id=args.pilot_area_id,
                working_crs=settings.working_crs,
            )
        )
        readiness = service.readiness(city_id=args.city_id)
        print(
            json.dumps(
                {
                    "build": result.model_dump(mode="json"),
                    "readiness": readiness.model_dump(mode="json"),
                },
                indent=2,
            )
        )
        if not readiness.technical_development_gate_passed:
            raise SystemExit("Sequence 7 reference bootstrap did not pass the development gate")
        if readiness.final_completion_gate_passed:
            print("Final real-pilot acceptance is already recorded.")
        else:
            print(
                "Reference validation passed; final human acceptance remains deferred "
                "to Sequence 20."
            )


if __name__ == "__main__":
    main()
