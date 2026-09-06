"""Controlled reference: 20 mm/h for three hours, rising stage and pump outage."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from floodguard.drainage.model_contracts import DrainModelInput
from floodguard.drainage.serialization import canonical_bytes, sha256
from floodguard.forcing.contracts import (
    BoundarySeries,
    BuildRequest,
    ControlSeries,
    ForcingWindow,
    Grid,
    Mode,
    RainInput,
    RainMember,
    Source,
)


def reference_request(twin_id: UUID, model: DrainModelInput) -> BuildRequest:
    issue = datetime(2026, 9, 6, 0, tzinfo=UTC)
    times = [issue + timedelta(hours=i) for i in range(4)]
    source = Source(
        source="reference://sequence-10",
        version="v1",
        quality="SYNTHETIC",
        sha256=sha256(canonical_bytes({"rain_mm_h": 20, "duration_h": 3})),
        method="Controlled 20 mm/h rectangular storm and declared reference stage/control.",
    )
    grid = Grid(
        horizontal_crs="EPSG:32645",
        x_edges_m=[299990, 300050, 300110],
        y_edges_m=[2499990, 2500030, 2500070],
    )
    rain = RainInput(
        mode=Mode.SYNTHETIC,
        issue_time=issue,
        time_edges=times,
        grid=grid,
        native_spatial_resolution_m=60,
        effective_spatial_resolution_m=60,
        source=source,
        ensemble_definition="Single controlled deterministic member.",
        members=[
            RainMember(
                member_id="deterministic",
                rain_rate_mm_h=[[[20.0, 20.0], [20.0, 20.0]] for _ in range(3)],
            )
        ],
    )
    boundaries = [
        BoundarySeries(
            boundary_id=o.drain_node_id,
            kind="OUTFALL_STAGE",
            time=times,
            stage_m=[1, 1.1, 1.2, 1.3],
            vertical_datum="SYNTHETIC_REFERENCE_DATUM",
            vertical_transform_status="COMPATIBLE",
            interpolation_method="LINEAR",
            source=source,
        )
        for o in model.definitions.outfalls
    ]
    controls = [
        ControlSeries(
            asset_id=p.drain_node_id,
            asset_kind="PUMP",
            control_kind="DISCRETE_STATE",
            time=times,
            operating_state=["ON", "OFF", "OFF", "ON"],
            control_value=[1, 0, 0, 1],
            interpolation_method="STEP_HOLD",
            source=source,
        )
        for p in model.definitions.pumps
    ]
    return BuildRequest(
        twin_id=twin_id,
        issue_time=issue,
        valid_from=issue,
        valid_to=times[-1],
        target_grid=Grid(
            horizontal_crs=grid.horizontal_crs,
            x_edges_m=[299990 + i * 10 for i in range(13)],
            y_edges_m=[2499990 + i * 10 for i in range(9)],
        ),
        forecast=ForcingWindow(rain=rain, boundaries=boundaries, controls=controls),
        antecedent_missing_reason="Forcing reference only; no hydraulic initial state inferred.",
    )
