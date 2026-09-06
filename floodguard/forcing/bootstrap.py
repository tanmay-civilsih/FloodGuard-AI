"""Build the controlled forcing benchmark and verify recreation in an empty package registry."""

import json
from typing import cast

from sqlalchemy import Table, create_engine
from sqlalchemy.orm import Session

from floodguard.drainage.model_contracts import DrainModelInput
from floodguard.forcing.factory import build_forcing_service
from floodguard.forcing.models import ForcingRecord
from floodguard.forcing.reference import reference_request
from floodguard.forcing.service import ForcingService
from floodguard.registry.database import get_session_factory
from floodguard.twin.reference import reference_snapshot
from floodguard.twin.snapshot import object_data


def main() -> None:
    with get_session_factory()() as session:
        service = build_forcing_service(session)
        snapshot = reference_snapshot()
        twin = service.twins.build(snapshot)
        model = DrainModelInput.model_validate(
            object_data(snapshot.evidence["drain-input"])["model"]
        )
        request = reference_request(twin.twin_id, model)
        built = service.build(request)
        payload = service.read_artifact(built.forcing_package_id, "manifest")
        engine = create_engine("sqlite://")
        ForcingRecord.metadata.create_all(engine, tables=[cast(Table, ForcingRecord.__table__)])
        with Session(engine) as empty:
            replica = ForcingService(empty, service.twins)
            recreated = replica.recreate(payload)
            if not recreated.created or recreated.forcing_package_id != built.forcing_package_id:
                raise ValueError("forcing recreation identity failed")
            if replica.read_artifact(recreated.forcing_package_id, "manifest") != payload:
                raise ValueError("forcing recreation bytes changed")
            if replica.recreate(payload).created:
                raise ValueError("forcing repeat recreation did not reuse identity")
        service.require_hydraulic_use(built.forcing_package_id, twin.twin_id)
        volume = built.quality_summary.rainfall_volume_m3_by_member["deterministic"]
        if abs(volume - 576.0) > 1e-9:
            raise ValueError("20 mm/h * 3 h * 9600 m2 benchmark must equal 576 m3")
        print(
            json.dumps(
                {
                    **built.model_dump(mode="json"),
                    "reference_twin_id": str(twin.twin_id),
                    "empty_database_recreation_verified": True,
                    "expected_rainfall_volume_m3": 576.0,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
