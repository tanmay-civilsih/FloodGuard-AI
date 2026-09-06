"""Explicit operator build, preview or recreation of immutable forcing packages."""

import argparse
from pathlib import Path

from floodguard.forcing.contracts import Assessment, BuildRequest, BuildResult, Manifest
from floodguard.forcing.factory import build_forcing_service
from floodguard.forcing.service import MAX_BYTES
from floodguard.registry.database import get_session_factory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--request", type=Path)
    group.add_argument("--recreate-manifest", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    path = args.request or args.recreate_manifest
    with path.open("rb") as stream:
        payload = stream.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise ValueError("forcing input exceeds prototype size bound")
    with get_session_factory()() as session:
        service = build_forcing_service(session)
        result: Assessment | BuildResult | Manifest
        if args.request:
            request = BuildRequest.model_validate_json(payload)
            result = service.preview(request) if args.dry_run else service.build(request)
        else:
            result = service.validate(payload) if args.dry_run else service.recreate(payload)
        print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
