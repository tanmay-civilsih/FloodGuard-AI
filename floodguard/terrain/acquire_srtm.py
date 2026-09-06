"""Automatically acquire the approved pilot's SRTM tile from ESA STEP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from floodguard.common.config import get_settings
from floodguard.registry.database import get_session_factory
from floodguard.registry.service import RegistryService
from floodguard.terrain.acquisition import TerrainAcquisitionRequest, plan_acquisition
from floodguard.terrain.assessment import (
    MAX_ASSESSMENT_BYTES,
    assessment_template,
    decode_assessment,
)
from floodguard.terrain.factory import build_terrain_acquirer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city-id", default="kolkata")
    parser.add_argument("--ward-id", default="7")
    parser.add_argument("--cell-size-m", type=float, default=30.0)
    parser.add_argument("--plan", action="store_true", help="show the tile without downloading")
    parser.add_argument("--dry-run", action="store_true", help="validate without persisting inputs")
    evidence = parser.add_mutually_exclusive_group()
    evidence.add_argument("--assessment", type=Path)
    evidence.add_argument("--assessment-template", type=Path)
    args = parser.parse_args()
    settings = get_settings()
    try:
        with get_session_factory()() as session:
            plan = plan_acquisition(
                session, TerrainAcquisitionRequest(
                    city_id=args.city_id, ward_id=args.ward_id, cell_size_m=args.cell_size_m,
                ), working_crs=settings.working_crs,
            )
            if args.plan:
                print(plan.model_dump_json(indent=2))
                return
            assessment = None
            if args.assessment:
                with args.assessment.open("rb") as handle:
                    assessment = decode_assessment(handle.read(MAX_ASSESSMENT_BYTES + 1))
            if args.assessment_template and args.assessment_template.exists():
                raise ValueError("assessment template already exists; choose a new path")

            def check_pilot() -> None:
                session.expire_all()
                current = plan_acquisition(session, plan.request, working_crs=settings.working_crs)
                if current != plan:
                    raise ValueError("the approved pilot changed during acquisition; retry")

            result = build_terrain_acquirer(session).acquire(
                RegistryService(session).get_source(plan.source_id), plan,
                assessment=assessment, check_pilot=check_pilot, progress=print,
                dry_run=args.dry_run or bool(args.assessment_template),
            )
            if args.assessment_template:
                with args.assessment_template.open("x", encoding="utf-8") as handle:
                    json.dump(
                        assessment_template(result.result.base_package_sha256), handle, indent=2
                    )
                print(f"Incomplete assessment form written to {args.assessment_template}")
            print(result.model_dump_json(indent=2))
            print("Terrain acquisition does not approve hydraulic readiness or freeze Sequence 6.")
    except (ValueError, RuntimeError, OSError, LookupError) as exc:
        raise SystemExit(f"Automatic terrain acquisition failed: {exc}") from exc


if __name__ == "__main__":
    main()
