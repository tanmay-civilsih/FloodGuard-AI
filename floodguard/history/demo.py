"""Prepare the documented real rainfall demonstration against an explicitly selected twin."""

import argparse
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from shapely.geometry import shape  # type: ignore[import-untyped]

from floodguard.forcing.contracts import Grid
from floodguard.history.contracts import EventRequest, PowerSelection
from floodguard.history.factory import build_history_service
from floodguard.registry.database import get_session_factory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--twin-id", required=True, type=UUID)
    parser.add_argument("--dataset-version-id", required=True, type=UUID)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    selection = PowerSelection.model_validate_json(args.selection.read_bytes())
    with get_session_factory()() as session:
        service = build_history_service(session)
        twin = service.forcing.twins.verify(service.forcing.twins.get(args.twin_id))
        if twin.evidence_scope.value != "REAL_PILOT_PROVISIONAL":
            raise ValueError("real rainfall demonstration requires an existing real pilot twin")
        version = service.harvester.get_version(args.dataset_version_id)
        if len(version.objects) != 1:
            raise ValueError("demo requires one bounded POWER response")
        x0, y0, x1, y1 = shape(twin.pilot_area.geometry).bounds
        request = EventRequest(
            event_key="kolkata-power-20210920-rainfall",
            title="Kolkata rainfall · 20 September 2021",
            catchment_id=twin.pilot_area.pilot_area_id,
            catchment_status="STUDY_AREA",
            catchment_evidence="Retained real twin study polygon; connected drainage unverified.",
            selection=selection,
            dataset_version_id=version.dataset_version_id,
            raw_object_id=version.objects[0].object_id,
            twin_id=twin.twin_id,
            replay_grid=Grid(
                horizontal_crs=twin.horizontal_crs, x_edges_m=[x0, x1], y_edges_m=[y0, y1]
            ),
            event_start=datetime(2021, 9, 20, tzinfo=UTC),
            event_end=datetime(2021, 9, 21, tzinfo=UTC),
            antecedent_hours=3,
            spatial_application_reason="One uniform coarse estimate over the small retained study "
            "area. No spatial rainfall detail is inferred.",
            evidence_gaps=[
                "DATA-08-01: source-bound adjacent-ward drainage to a destination unresolved.",
                "No measured flood depths/extents or numerical local gauge/radar archive acquired.",
                "Historical provider availability unknown; strict issue-time backtest ineligible.",
                "Event-date drain condition, pump operations and downstream stages are missing.",
                "MERRA-2 is coarse reanalysis; street-scale rainfall skill unestablished.",
            ],
            infrastructure_assumptions=[
                "The later-built twin is static context; 2021 infrastructure is unverified.",
                "No initialized hydraulic state or continuity between simulations is claimed.",
            ],
        )
        service.preview(request)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(request.model_dump_json(indent=2), encoding="utf-8")
        print(f"Wrote checked rainfall-only request {args.output}")


if __name__ == "__main__":
    main()
