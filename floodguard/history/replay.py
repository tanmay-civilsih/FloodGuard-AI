"""Explicit application of coarse point-extracted reanalysis to a small study grid."""

from datetime import datetime, timedelta
from itertools import pairwise
from math import hypot

from pyproj import Transformer

from floodguard.forcing.contracts import (
    BuildRequest,
    ForcingWindow,
    Mode,
    RainInput,
    RainMember,
    Source,
)
from floodguard.history.contracts import EventRequest, ObservationRecord
from floodguard.history.power import RESOLUTION_M


def validate_application(request: EventRequest) -> None:
    """Bound a uniform study-area assumption, not invented native radar spatial detail."""
    grid = request.replay_grid
    project = Transformer.from_crs("EPSG:4326", grid.horizontal_crs, always_xy=True)
    px, py = project.transform(request.selection.longitude, request.selection.latitude)
    corners = [
        (x, y)
        for x in (grid.x_edges_m[0], grid.x_edges_m[-1])
        for y in (grid.y_edges_m[0], grid.y_edges_m[-1])
    ]
    if any(hypot(x - px, y - py) > 25000 for x, y in corners):
        raise ValueError("uniform regional estimate limited to 25 km from selected point")


def rain(
    request: EventRequest,
    records: list[ObservationRecord],
    source: Source,
    start: datetime,
    end: datetime,
) -> RainInput:
    selected = [r for r in records if start <= r.interval_start < end]
    if (
        not selected
        or selected[0].interval_start != start
        or selected[-1].interval_end != end
        or any(a.interval_end != b.interval_start for a, b in pairwise(selected))
        or any(r.value is None or r.qc != "VALID" for r in selected)
    ):
        raise ValueError("incomplete rainfall cannot be filled with zero")
    grid = request.replay_grid
    nx, ny = len(grid.x_edges_m) - 1, len(grid.y_edges_m) - 1
    return RainInput(
        mode=Mode.REPLAY,
        # Historical window label only. Availability resides in the event manifest.
        issue_time=start,
        time_edges=[r.interval_start for r in selected] + [end],
        grid=grid,
        native_spatial_resolution_m=RESOLUTION_M,
        effective_spatial_resolution_m=RESOLUTION_M,
        source=source,
        ensemble_definition="Single coarse reanalysis estimate; no ensemble probability.",
        members=[
            RainMember(
                member_id="reanalysis",
                rain_rate_mm_h=[
                    [[float(r.value) for _ in range(nx)] for _ in range(ny)]  # type: ignore[arg-type]
                    for r in selected
                ],
            )
        ],
    )


def window_request(
    request: EventRequest,
    records: list[ObservationRecord],
    source: Source,
    start: datetime,
    end: datetime,
) -> BuildRequest:
    validate_application(request)
    forcing = ForcingWindow(rain=rain(request, records, source, start, end))
    antecedent = None
    reason = "No antecedent requested; no dry initial state inferred."
    if request.antecedent_hours:
        try:
            antecedent = ForcingWindow(
                rain=rain(
                    request,
                    records,
                    source,
                    start - timedelta(hours=request.antecedent_hours),
                    start,
                )
            )
        except ValueError:
            reason = "Declared antecedent contains missing/rejected intervals; state is unknown."
    return BuildRequest(
        twin_id=request.twin_id,
        issue_time=start,
        valid_from=start,
        valid_to=end,
        target_grid=request.replay_grid,
        forecast=forcing,
        antecedent=antecedent,
        antecedent_missing_reason=reason if antecedent is None else None,
    )
