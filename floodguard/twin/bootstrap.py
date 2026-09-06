"""Build and independently recreate the reference and explicitly selected real pilot snapshot."""

import argparse
import json
from typing import cast
from uuid import UUID

from sqlalchemy import Table, create_engine
from sqlalchemy.orm import Session

from floodguard.registry.database import get_session_factory
from floodguard.twin.contracts import PilotArea, TwinBuildRequest
from floodguard.twin.factory import build_source_loader, build_twin_service
from floodguard.twin.models import TwinRecord
from floodguard.twin.reference import reference_snapshot
from floodguard.twin.repository import TwinRepository
from floodguard.twin.service import TwinService
from floodguard.urban_gis.reference import _polygon


def pilot_request() -> TwinBuildRequest:
    """Exact already-stored versions; absence is explicit, never resolved with latest queries."""
    return TwinBuildRequest(
        city_id="kolkata",
        horizontal_crs="EPSG:32645",
        pilot_area=PilotArea(
            pilot_area_id="kolkata-ward-7",
            geometry=_polygon(640200, 2499810, 641460, 2500770),
            ward_ids=["7", "8", "10", "12"],
        ),
        terrain_id=UUID("302999c4-68d7-5dc9-bdd3-b12fd41c13d6"),
        urban_gis_id=None,
        drain_product_id=UUID("30c05f00-2ab5-5aea-a640-5275711ce127"),
        ward_id=UUID("acff42f4-d7a0-5bed-bcdc-28d5ed740b63"),
        catchment_id=UUID("9db50e2f-b853-5500-8a3d-7e507c78e40c"),
        waterbody_id=UUID("2d93a6a7-6357-50b5-9839-766c5b6b9340"),
        missing_reasons={
            "urban_gis": "Real urban GIS is absent; reference substitution is forbidden."
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city-id", default="kolkata", choices=["kolkata"])
    parser.parse_args()
    with get_session_factory()() as session:
        service = build_twin_service(session)
        reference = service.build(reference_snapshot())
        real = service.build(build_source_loader(session).load(pilot_request()))
        results = []
        engine = create_engine("sqlite://")
        TwinRecord.metadata.create_all(engine, tables=[cast(Table, TwinRecord.__table__)])
        # An empty metadata DB proves recreation does not reuse existing twin registrations.
        with Session(engine) as fresh:
            replica = TwinService(
                TwinRepository(fresh),
                service.store,
                working_crs=service.working_crs,
                software_version="recreation-reader",
                software_source_sha256="0" * 64,
                max_bytes=service.max_bytes,
            )
            for built in (reference, real):
                payload = service.read_artifact(built.twin_id, "manifest")
                recreated = replica.recreate(payload)
                if not recreated.created or recreated.twin_id != built.twin_id:
                    raise ValueError("independent twin recreation did not preserve identity")
                if replica.read_artifact(built.twin_id, "manifest") != payload:
                    raise ValueError("recreated twin manifest bytes changed")
                if service.recreate(payload).created:
                    raise ValueError("repeat recreation must reuse exact twin identity")
                results.append(
                    {**built.model_dump(mode="json"), "empty_database_recreation_verified": True}
                )
        readiness = service.readiness("kolkata")
        print(
            json.dumps({"twins": results, "readiness": readiness.model_dump(mode="json")}, indent=2)
        )
        if not readiness.assembly_development_gate_passed:
            raise SystemExit("Twin assembly/recreation development gate failed")
        if not readiness.technical_development_gate_passed:
            print("ASSEMBLY PASSED; freeze requires genuine real cross-ward evidence.")


if __name__ == "__main__":
    main()
