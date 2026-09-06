"""Explicit operator CLI for source import and applying a complete binding plan."""

import argparse
import json
from pathlib import Path
from uuid import UUID

from floodguard.drainage.factory import build_drain_service
from floodguard.drainage.importer import bind_graph, import_sources
from floodguard.drainage.model_contracts import DrainImportDraft, ImportBindingPlan, WardBoundarySet
from floodguard.drainage.serialization import decode_object
from floodguard.drainage.source_loader import load_pilot_sources
from floodguard.reconstruction.factory import build_reconstruction_service
from floodguard.registry.database import get_session_factory
from floodguard.spatial.factory import build_spatial_service


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city-id", default="kolkata")
    parser.add_argument("--ward-id", default="7")
    parser.add_argument("--reconstruction-id", type=UUID)
    parser.add_argument("--normalization-id", type=UUID)
    parser.add_argument("--binding-plan", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    with get_session_factory()() as session:
        service = build_drain_service(session)
        if args.binding_plan is not None:
            with args.binding_plan.open("rb") as stream:
                content = decode_object(stream.read(service.max_bytes + 1), service.max_bytes)
            plan = ImportBindingPlan.model_validate(content)
            if args.dry_run:
                record = service.get(plan.draft_id)
                if record.fingerprint != plan.draft_fingerprint:
                    raise ValueError("binding plan draft fingerprint mismatch")
                service.verify(record)
                draft = DrainImportDraft.model_validate_json(
                    service.read_artifact(plan.draft_id, "draft")
                )
                wards = WardBoundarySet.model_validate_json(
                    service.read_artifact(plan.draft_id, "wards")
                )
                from floodguard.drainage.assessment import assess

                print(assess(bind_graph(draft, wards, plan)).model_dump_json(indent=2))
            else:
                print(service.build_bound(plan).model_dump_json(indent=2))
        else:
            sources = load_pilot_sources(
                build_reconstruction_service(session),
                build_spatial_service(session),
                city_id=args.city_id,
                ward_id=args.ward_id,
                max_bytes=service.max_bytes,
                reconstruction_id=args.reconstruction_id,
                normalization_id=args.normalization_id,
            )
            if args.dry_run:
                draft, _ = import_sources(*sources, max_bytes=service.max_bytes)
                print(
                    json.dumps(
                        {
                            "source_info": draft.source_info.model_dump(mode="json"),
                            "features": len(draft.features),
                            "unresolved_items": draft.unresolved_items,
                        },
                        indent=2,
                    )
                )
            else:
                print(service.import_draft(*sources).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
