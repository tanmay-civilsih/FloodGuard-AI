"""Operator-only explicit twin selection, dry-run assessment and manifest recreation."""

import argparse
from pathlib import Path

from floodguard.drainage.serialization import decode_object
from floodguard.registry.database import get_session_factory
from floodguard.twin.contracts import TwinBuildRequest
from floodguard.twin.factory import build_source_loader, build_twin_service
from floodguard.twin.snapshot import evaluate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    selected = parser.add_mutually_exclusive_group(required=True)
    selected.add_argument("--request", type=Path)
    selected.add_argument("--recreate-manifest", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    with get_session_factory()() as session:
        service = build_twin_service(session)
        path = args.request or args.recreate_manifest
        with path.open("rb") as stream:
            payload = stream.read(service.max_bytes + 1)
        if args.request:
            request = TwinBuildRequest.model_validate(decode_object(payload, service.max_bytes))
            snapshot = build_source_loader(session).load(request)
            if args.dry_run:
                blockers, compatible, cross = evaluate(snapshot)
                import json

                print(
                    json.dumps(
                        {
                            "scenario_blockers": blockers,
                            "compatible_vertical_reference": compatible,
                            "real_cross_ward_path_available": cross,
                            "persisted": False,
                        },
                        indent=2,
                    )
                )
            else:
                print(service.build(snapshot).model_dump_json(indent=2))
        elif args.dry_run:
            print(service.validate_manifest(payload).model_dump_json(indent=2))
        else:
            print(service.recreate(payload).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
