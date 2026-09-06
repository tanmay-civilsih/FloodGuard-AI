"""Explicit local reference build and existing real-pilot import; no external acquisition."""

import argparse
import json

from floodguard.common.config import get_settings
from floodguard.drainage.factory import build_drain_service
from floodguard.drainage.reference import reference_model
from floodguard.drainage.source_loader import load_pilot_sources
from floodguard.reconstruction.factory import build_reconstruction_service
from floodguard.registry.database import get_session_factory
from floodguard.spatial.factory import build_spatial_service


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city-id", default="kolkata")
    parser.add_argument("--ward-id", default="7")
    args = parser.parse_args()
    settings = get_settings()
    with get_session_factory()() as session:
        service = build_drain_service(session)
        sources = load_pilot_sources(
            build_reconstruction_service(session),
            build_spatial_service(session),
            city_id=args.city_id,
            ward_id=args.ward_id,
            max_bytes=service.max_bytes,
        )
        imported = service.import_draft(*sources)
        reference = service.build_reference(reference_model(args.city_id, settings.working_crs))
        reused_import = service.import_draft(*sources)
        reused_reference = service.build_reference(
            reference_model(args.city_id, settings.working_crs)
        )
        if reused_import.created or reused_reference.created:
            raise SystemExit("Repeated identical bootstrap must reuse immutable products")
        readiness = service.readiness(args.city_id)
        print(
            json.dumps(
                {
                    "import": imported.model_dump(mode="json"),
                    "reference": reference.model_dump(mode="json"),
                    "idempotency_verified": True,
                    "readiness": readiness.model_dump(mode="json"),
                },
                indent=2,
            )
        )
        if not readiness.technical_development_gate_passed:
            raise SystemExit("Sequence 8 automated development bootstrap failed")


if __name__ == "__main__":
    main()
