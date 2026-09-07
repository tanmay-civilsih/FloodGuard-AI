"""Sequence 10 scientific contracts, immutable persistence, and no-extrapolation behavior."""

import json
from datetime import timedelta
from uuid import UUID

import numpy as np
import pytest
import xarray as xr
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from zarr.storage import ZipStore

from apps.api.main import app
from apps.api.routers.forcing import get_forcing_service
from floodguard.drainage.model_contracts import DrainModelInput
from floodguard.drainage.serialization import canonical_bytes
from floodguard.forcing.assessment import (
    control_at,
    interpolate,
    normalized_stage,
    window_assessment,
)
from floodguard.forcing.contracts import BuildRequest, Coverage, Mode, RainInput
from floodguard.forcing.models import ForcingRecord
from floodguard.forcing.rain import remap, zarr_bytes
from floodguard.forcing.reference import reference_request
from floodguard.forcing.service import ForcingService, identity
from floodguard.twin.reference import reference_snapshot
from tests.twin_fixtures import twin_service


@pytest.fixture
def context():
    twins, session, store = twin_service()
    snapshot = reference_snapshot()
    twin = twins.build(snapshot)
    model = DrainModelInput.model_validate(json.loads(snapshot.evidence["drain-input"])["model"])
    request = reference_request(twin.twin_id, model)
    yield ForcingService(session, twins), request, store
    session.close()


def checked(request):
    return BuildRequest.model_validate_json(request.model_dump_json())


def test_interpretable_storm_and_xarray_roundtrip(context, tmp_path):
    service, request, _ = context
    result = remap(request.forecast.rain, request.target_grid)
    assert result.volumes == pytest.approx({"deterministic": 576.0})
    np.testing.assert_allclose(result.accumulation[-1], 60.0)
    payload = zarr_bytes(request.forecast.rain, request.target_grid, result)
    assert payload == zarr_bytes(request.forecast.rain, request.target_grid, result)
    path = tmp_path / "rain.zarr.zip"
    path.write_bytes(payload)
    with ZipStore(path, mode="r") as store, xr.open_zarr(store, chunks=None) as dataset:
        assert dataset.rain_rate.dims == ("time", "y", "x")
        assert dataset.rain_rate.shape == (3, 8, 12)
        np.testing.assert_allclose(dataset.accumulation[-1], 60)
        assert dataset.attrs["effective_spatial_resolution_m"] == 60
        assert dataset.attrs["native_spatial_resolution_m"] == 60
        assert dataset.rain_rate.attrs["units"] == "mm/h"
        assert np.all(np.isfinite(dataset.quality_flag))
        assert str(dataset.time.values[0]).startswith("2026-09-06T00:00:00")
    assert service.preview(request).hydraulic_use_eligible


def test_irregular_intervals_nonuniform_rain_and_ensemble(context, tmp_path):
    _, request, _ = context
    rain = request.forecast.rain
    start = rain.time_edges[0]
    rain.time_edges = [start + timedelta(seconds=s) for s in (0, 600, 1800, 10800)]
    rain.members[0].rain_rate_mm_h = [[[10, 20], [30, 40]]] * 3
    second = rain.members[0].model_copy(deep=True)
    second.member_id = "dry"
    second.rain_rate_mm_h = [[[0, 0], [0, 0]]] * 3
    rain.members.append(second)
    result = remap(rain, request.target_grid)
    assert result.volumes == pytest.approx({"deterministic": 720.0, "dry": 0.0})
    path = tmp_path / "ensemble.zip"
    path.write_bytes(zarr_bytes(rain, request.target_grid, result))
    with ZipStore(path, mode="r") as store, xr.open_zarr(store, chunks=None) as data:
        assert data.rain_rate.dims == ("time", "y", "x", "ensemble_member")
        assert np.all(data.rain_rate[..., 1] == 0)
        assert np.all(np.isfinite(data.rain_rate))


@pytest.mark.parametrize(
    "mutation",
    [
        "negative",
        "nan",
        "shape",
        "duplicate_time",
        "naive",
        "wrong_units",
        "resolution",
        "duplicate_member",
        "false_operational",
        "radar_lineage",
        "blend_lineage",
        "unknown_field",
    ],
)
def test_rain_input_rejections(context, mutation):
    _, request, _ = context
    data = request.forecast.rain.model_dump(mode="json")
    if mutation == "negative":
        data["members"][0]["rain_rate_mm_h"][0][0][0] = -1
    elif mutation == "nan":
        data["members"][0]["rain_rate_mm_h"][0][0][0] = float("nan")
    elif mutation == "shape":
        data["members"][0]["rain_rate_mm_h"] = [[[1]]]
    elif mutation == "duplicate_time":
        data["time_edges"][1] = data["time_edges"][0]
    elif mutation == "naive":
        data["time_edges"][0] = "2026-09-06T00:00:00"
    elif mutation == "wrong_units":
        data["units"] = "m/s"
    elif mutation == "resolution":
        data["effective_spatial_resolution_m"] = 1
    elif mutation == "duplicate_member":
        data["members"] *= 2
    elif mutation == "false_operational":
        data["mode"] = "EXTERNAL_FORECAST"
    elif mutation in {"radar_lineage", "blend_lineage"}:
        data["mode"] = "RADAR_NOWCAST" if mutation == "radar_lineage" else "RADAR_NWP_BLEND"
        data["source"]["quality"] = "PROVISIONAL"
    else:
        data["hidden_padding"] = True
    with pytest.raises(ValueError):
        RainInput.model_validate(data)


@pytest.mark.parametrize("mutation", ["outside", "different_crs", "unequal_footprint"])
def test_rain_grid_rejects_unsupported_coverage(context, mutation):
    service, request, _ = context
    if mutation == "outside":
        request.target_grid.x_edges_m = [300000, 300010]
    elif mutation == "different_crs":
        request.forecast.rain.grid.horizontal_crs = "EPSG:32644"
    else:
        request.forecast.rain.grid.x_edges_m = [299980, 300040, 300100]
    with pytest.raises(ValueError):
        service.preview(checked(request))


@pytest.mark.parametrize("seconds, expected", [(5400, Coverage.PARTIAL), (10800, Coverage.FULL)])
def test_short_forecast_never_extended(context, seconds, expected):
    service, request, _ = context
    rain = request.forecast.rain
    rain.time_edges = [rain.issue_time + timedelta(seconds=seconds * i / 3) for i in range(4)]
    result = service.preview(checked(request))
    assert result.coverage is expected
    assert result.common_valid_to == rain.time_edges[-1]
    assert result.hydraulic_use_eligible is (expected is Coverage.FULL)


def test_disjoint_forecast_insufficient(context):
    service, request, _ = context
    request.forecast.rain.time_edges = [
        t + timedelta(hours=4) for t in request.forecast.rain.time_edges
    ]
    result = service.preview(checked(request))
    assert result.coverage is Coverage.INSUFFICIENT
    assert result.common_valid_to is None


@pytest.mark.parametrize("kind", ["boundary", "control"])
def test_missing_and_partial_required_series(context, kind):
    service, request, _ = context
    series = request.forecast.boundaries if kind == "boundary" else request.forecast.controls
    # The reference's free outfall becomes a supplied dynamic boundary and constrains support.
    series[0].time[-1] -= timedelta(minutes=30)
    result = service.preview(checked(request))
    assert result.coverage is Coverage.PARTIAL
    if kind == "control":
        series.clear()
        result = service.preview(checked(request))
        assert result.coverage is Coverage.INSUFFICIENT
        assert any("Missing required control" in b for b in result.blockers)


@pytest.mark.parametrize("method, expected", [("LINEAR", 1.05), ("STEP_HOLD", 1)])
def test_stage_interpolation(context, method, expected):
    _, request, _ = context
    b = request.forecast.boundaries[0]
    assert interpolate(b.time, b.stage_m, b.time[0] + timedelta(minutes=30), method) == expected
    assert interpolate(b.time, b.stage_m, b.time[-1], method) == b.stage_m[-1]
    for t in (b.time[0] - timedelta(seconds=1), b.time[-1] + timedelta(seconds=1)):
        with pytest.raises(ValueError, match="extrapolation"):
            interpolate(b.time, b.stage_m, t, method)


def test_pump_discontinuity_exact_knot(context):
    _, request, _ = context
    c = request.forecast.controls[0]
    assert (
        interpolate(c.time, c.control_value, c.time[1] - timedelta(microseconds=1), "STEP_HOLD")
        == 1
    )
    assert interpolate(c.time, c.control_value, c.time[1], "STEP_HOLD") == 0
    c.interpolation_method = "LINEAR"
    with pytest.raises(ValueError, match="STEP_HOLD"):
        checked(request)


def test_explicit_datum_transform_applied_once(context):
    service, request, _ = context
    b = request.forecast.boundaries[0]
    b.vertical_transform_status = "TRANSFORMED"
    b.target_vertical_datum = b.vertical_datum
    b.vertical_datum = "OTHER_REFERENCE"
    b.vertical_offset_m = 2.0
    b.transform_method = "Controlled reference offset, not a real survey transformation."
    assert normalized_stage(b, "SYNTHETIC_REFERENCE_DATUM") == [3, 3.1, 3.2, 3.3]
    assert b.stage_m == [1, 1.1, 1.2, 1.3]
    assert service.preview(checked(request)).hydraulic_use_eligible


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_datum",
        "unresolved",
        "wrong_boundary",
        "wrong_asset",
        "gate",
        "missing_transform",
        "state_mismatch",
        "future_issue",
    ],
)
def test_boundary_control_and_issue_rejections(context, mutation):
    service, request, _ = context
    b, c = request.forecast.boundaries[0], request.forecast.controls[0]
    if mutation == "wrong_datum":
        b.vertical_datum = "UNKNOWN_DATUM"
    elif mutation == "unresolved":
        b.vertical_transform_status = "UNRESOLVED"
    elif mutation == "wrong_boundary":
        b.boundary_id = "not-in-twin"
    elif mutation == "wrong_asset":
        c.asset_id = "not-in-twin"
    elif mutation == "gate":
        c.asset_kind = "GATE"
    elif mutation == "missing_transform":
        b.vertical_transform_status = "TRANSFORMED"
    elif mutation == "state_mismatch":
        c.operating_state[0] = "OFF"
    else:
        request.issue_time -= timedelta(hours=1)
    with pytest.raises(ValueError):
        service.preview(checked(request))


def test_antecedent_complete_and_incomplete(context):
    service, request, _ = context
    ant = request.forecast.model_copy(deep=True)
    ant.rain.issue_time -= timedelta(hours=3)
    ant.rain.time_edges = [t - timedelta(hours=3) for t in ant.rain.time_edges]
    for s in [*ant.boundaries, *ant.controls]:
        s.time = [t - timedelta(hours=3) for t in s.time]
    request.antecedent, request.antecedent_missing_reason = ant, None
    assert service.preview(checked(request)).antecedent_status == "COMPLETE"
    ant.controls.clear()
    assert service.preview(checked(request)).antecedent_status == "INCOMPLETE"
    ant.rain.time_edges[-1] -= timedelta(seconds=1)
    with pytest.raises(ValueError, match="antecedent"):
        checked(request)


def test_build_reuse_and_empty_registry_recreation(context):
    service, request, _ = context
    built = service.build(request)
    assert built.created
    assert not service.build(request).created
    payload = service.read_artifact(built.forcing_package_id, "manifest")
    engine = create_engine("sqlite://")
    ForcingRecord.__table__.create(engine)
    with Session(engine) as session:
        replica = ForcingService(session, service.twins)
        assert replica.recreate(payload).created
        assert replica.read_artifact(built.forcing_package_id, "manifest") == payload
        assert not replica.recreate(payload).created
    service.require_hydraulic_use(built.forcing_package_id, request.twin_id)
    with pytest.raises(ValueError):
        service.require_hydraulic_use(built.forcing_package_id, UUID(int=1))
    request.forecast.rain.members[0].rain_rate_mm_h[0][0][0] = 21
    assert service.build(request).forcing_package_id != built.forcing_package_id


@pytest.mark.parametrize(
    "artifact",
    [
        "rain.zarr.zip",
        "boundaries-and-controls.json",
        "request.json",
        "twin-manifest.json",
        "antecedent.json",
        "manifest",
    ],
)
def test_corruption_fails_closed(context, artifact):
    service, request, store = context
    built = service.build(request)
    record = service.get(built.forcing_package_id)
    manifest = service.verify(record)
    ref = record.manifest if artifact == "manifest" else manifest.artifacts[artifact]
    store.spatial_objects[ref.object_key] = b"corrupt"
    with pytest.raises(ValueError):
        service.read_artifact(built.forcing_package_id, "manifest")
    with pytest.raises(ValueError):
        service.build(request)


def test_rehashed_false_assessment_rejected(context):
    service, request, _ = context
    built = service.build(request)
    manifest = service.verify(service.get(built.forcing_package_id))
    manifest.quality_summary.rainfall_volume_m3_by_member["deterministic"] = 1
    manifest.forcing_package_id = identity(manifest)[0]
    with pytest.raises(ValueError, match="assessment"):
        service.recreate(canonical_bytes(manifest.model_dump(mode="json")))


def test_partial_package_stored_but_hydraulic_use_refused(context):
    service, request, _ = context
    request.forecast.rain.time_edges[-1] -= timedelta(minutes=30)
    built = service.build(checked(request))
    assert built.quality_summary.coverage is Coverage.PARTIAL
    with pytest.raises(ValueError, match="ineligible"):
        service.require_hydraulic_use(built.forcing_package_id, request.twin_id)


def test_api_reads_and_corruption(context):
    service, request, store = context
    built = service.build(request)
    app.dependency_overrides[get_forcing_service] = lambda: service
    try:
        with TestClient(app) as client:
            prefix = f"/forcing/products/{built.forcing_package_id}"
            assert client.get(prefix).status_code == 200
            assert client.get(prefix + "/manifest").status_code == 200
            response = client.get(prefix + "/rain.zarr.zip")
            assert (
                response.status_code == 200
                and response.headers["content-type"] == "application/zip"
            )
            assert client.get(prefix + "/missing").status_code == 404
            assert client.get("/forcing/products/invalid").status_code == 422
            assert client.get("/forcing/products?city_id=kolkata").status_code == 200
            record = service.get(built.forcing_package_id)
            store.spatial_objects[record.manifest.object_key] = b"bad"
            assert client.get(prefix + "/manifest").status_code == 409
            del store.spatial_objects[record.manifest.object_key]
            assert client.get(prefix + "/manifest").status_code == 503
    finally:
        app.dependency_overrides.pop(get_forcing_service, None)


def test_preview_writes_nothing(context):
    service, request, store = context
    before = dict(store.spatial_objects)
    service.preview(request)
    assert before == store.spatial_objects
    assert service.list("kolkata") == []


@pytest.mark.parametrize(
    "mode", [Mode.REPLAY, Mode.EXTERNAL_FORECAST, Mode.RADAR_NOWCAST, Mode.RADAR_NWP_BLEND]
)
def test_prepared_source_modes_and_explicit_blend_coverage(context, mode):
    service, request, _ = context
    rain = request.forecast.rain
    rain.mode = mode
    rain.source.quality = "PROVISIONAL"
    rain.source.method = "Test-only prepared input adapter; no acquired operational source claim."
    rain.processing_lineage = [rain.source.model_copy(deep=True)]
    if mode is Mode.RADAR_NWP_BLEND:
        second = rain.source.model_copy(deep=True)
        second.source = "test://nwp-source"
        rain.processing_lineage.append(second)
    result = service.preview(checked(request))
    assert result.coverage is (Coverage.BLENDED if mode is Mode.RADAR_NWP_BLEND else Coverage.FULL)
    assert result.hydraulic_use_eligible
    if mode is Mode.RADAR_NWP_BLEND:
        rain.processing_lineage[1] = rain.processing_lineage[0]
        with pytest.raises(ValueError, match="distinct"):
            checked(request)


def test_continuous_control_keeps_discrete_availability(context):
    _, request, _ = context
    series = request.forecast.controls[0]
    series.control_kind = "CONTINUOUS_FRACTION"
    series.interpolation_method = "LINEAR"
    series.control_value = [0.5, 0, 0, 1]
    assert control_at(series, series.time[0] + timedelta(minutes=30)) == ("ON", 0.25)
    assert control_at(series, series.time[2] + timedelta(minutes=30)) == ("OFF", 0)
    assert control_at(series, series.time[-1]) == ("ON", 1)


def test_required_fixed_stage_cannot_be_omitted(context):
    _, request, _ = context
    snapshot = reference_snapshot()
    model = DrainModelInput.model_validate(json.loads(snapshot.evidence["drain-input"])["model"])
    model.definitions.outfalls[0].boundary_type = "FIXED_STAGE"
    request.forecast.boundaries.clear()
    result = window_assessment(
        request.forecast, request.valid_from, request.valid_to, model, "SYNTHETIC_REFERENCE_DATUM"
    )
    assert result[0] is Coverage.INSUFFICIENT
    assert any("Missing required boundary" in b for b in result[3])


@pytest.mark.parametrize("retained_draft", [False, True])
def test_visual_twin_remains_ineligible(context, retained_draft):
    from floodguard.twin.contracts import ComponentRole as R

    service, request, _ = context
    snapshot = reference_snapshot()
    for role in (R.DRAIN_GRAPH, R.EXCHANGE, R.PARAMETERS, R.PUMP):
        del snapshot.components[role]
        del snapshot.sources[role]
        snapshot.missing[role] = "Controlled missing-component test."
    snapshot.evidence.pop("drain-input")
    if retained_draft:
        snapshot.evidence["drain-input"] = canonical_bytes({
            "source_info": {"evidence": "imported linework only; no assembled model"}
        })
    built = service.twins.build(snapshot)
    request.twin_id = built.twin_id
    request.forecast.boundaries.clear()
    request.forecast.controls.clear()
    result = service.preview(request)
    assert result.coverage is Coverage.INSUFFICIENT
    assert not result.hydraulic_use_eligible
    assert any("not scenario-ready" in b for b in result.blockers)


def test_retained_twin_corruption_blocks_forcing(context):
    service, request, store = context
    built = service.build(request)
    twin = service.twins.verify(service.twins.get(request.twin_id))
    ref = twin.ward_version.artifact
    store.spatial_objects[ref.object_key] = b"bad"
    with pytest.raises(ValueError):
        service.require_hydraulic_use(built.forcing_package_id, request.twin_id)


def test_rehashed_generated_rain_tampering_is_rejected(context):
    service, request, _ = context
    built = service.build(request)
    manifest = service.verify(service.get(built.forcing_package_id))
    manifest.artifacts["rain.zarr.zip"] = service.write_blob(b"not the computed rain")
    manifest.forcing_package_id = identity(manifest)[0]
    with pytest.raises(ValueError, match="deterministic"):
        service.recreate(canonical_bytes(manifest.model_dump(mode="json")))


def test_antecedent_package_recreation(context):
    service, request, _ = context
    ant = request.forecast.model_copy(deep=True)
    ant.rain.issue_time -= timedelta(hours=3)
    ant.rain.time_edges = [t - timedelta(hours=3) for t in ant.rain.time_edges]
    for series in [*ant.boundaries, *ant.controls]:
        series.time = [t - timedelta(hours=3) for t in series.time]
    request.antecedent, request.antecedent_missing_reason = ant, None
    built = service.build(checked(request))
    assert built.quality_summary.antecedent_status == "COMPLETE"
    assert service.read_artifact(built.forcing_package_id, "antecedent-rain.zarr.zip")[:2] == b"PK"
    assert not service.recreate(service.read_artifact(built.forcing_package_id, "manifest")).created
