"""Operator-only acquisition, event build/recreation, preview export and split validation."""

import argparse
import json
from pathlib import Path
from uuid import UUID

from floodguard.history.acquire import acquire_power
from floodguard.history.contracts import EvaluationDatasetDefinition, EventRequest, PowerSelection
from floodguard.history.factory import build_history_service
from floodguard.history.preview import render_preview
from floodguard.registry.database import get_session_factory
from floodguard.registry.service import RegistryService


def read(path: Path) -> bytes:
    with path.open("rb") as stream:
        payload = stream.read(2_000_001)
    if len(payload) > 2_000_000:
        raise ValueError("historical operator input exceeds 2 MB")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--acquire-power", type=Path)
    group.add_argument("--request", type=Path)
    group.add_argument("--recreate-manifest", type=Path)
    group.add_argument("--export-preview", type=UUID)
    group.add_argument("--validate-dataset", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    if args.dry_run and not (args.request or args.recreate_manifest):
        parser.error("--dry-run requires --request or --recreate-manifest")
    if args.refresh and not args.acquire_power:
        parser.error("--refresh requires --acquire-power")
    if args.export_preview and not args.output:
        parser.error("--export-preview requires --output")
    if args.validate_dataset:
        definition = EvaluationDatasetDefinition.model_validate_json(read(args.validate_dataset))
        output = json.dumps(
            {
                "definition": definition.model_dump(mode="json"),
                "split_sha256": definition.split_hash(),
            },
            indent=2,
        )
    else:
        with get_session_factory()() as session:
            service = build_history_service(session)
            if args.acquire_power:
                selection = PowerSelection.model_validate_json(read(args.acquire_power))
                output = acquire_power(
                    RegistryService(session),
                    service.harvester,
                    selection,
                    refresh=args.refresh,
                ).model_dump_json(indent=2)
            elif args.request:
                request = EventRequest.model_validate_json(read(args.request))
                output = (
                    json.dumps(service.preview(request), indent=2)
                    if args.dry_run
                    else service.build(request).model_dump_json(indent=2)
                )
            elif args.recreate_manifest:
                operation = service.validate if args.dry_run else service.recreate
                output = operation(read(args.recreate_manifest)).model_dump_json(indent=2)
            else:
                output = render_preview(service.view(args.export_preview))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
