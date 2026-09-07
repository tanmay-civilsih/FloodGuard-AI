"""Sequence 11 real provider units plus controlled integrity and scientific failure checks."""

import json
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.routers.history import get_history_service
from floodguard.drainage.serialization import canonical_bytes, sha256
from floodguard.forcing.contracts import BuildRequest, Manifest
from floodguard.forcing.service import identity as forcing_identity
from floodguard.history.acquire import acquire_power
from floodguard.history.contracts import (
    EvaluationDatasetDefinition,
    EventRequest,
    ObservationRecord,
    PowerSelection,
    SourceAvailabilityRecord,
)
from floodguard.history.models import HistoricalEventRecord
from floodguard.history.observations import counter_increment, deduplicate, rate_mm_h
from floodguard.history.power import decode_power, source_definition
from floodguard.history.preview import render_preview
from floodguard.history.service import identity
from floodguard.history.stations import StationInterval, normalize_stations
from floodguard.registry.contracts import SourceReplace
from floodguard.registry.service import RegistryService
from tests.history_fixtures import FIXTURES, history_context, utc


def availability(**overrides):
    return SourceAvailabilityRecord(
        **(
            {
                "source_id": uuid4(),
                "dataset_version_id": uuid4(),
                "source_revision": "archive-v1",
                "acquired_at": utc("2026-09-07T00:00Z"),
                "valid_from": utc("2021-09-19T00:00Z"),
                "valid_to": utc("2021-09-22T00:00Z"),
                "availability_status": "UNKNOWN",
                "availability_evidence": "No historical publication receipt.",
            }
            | overrides
        )
    )


def selection():
    return PowerSelection(
        longitude=88.3639,
        latitude=22.5726,
        start=utc("2021-09-19T00:00Z"),
        end=utc("2021-09-22T00:00Z"),
    )


def decoded():
    return decode_power((FIXTURES / "power-hourly.json").read_bytes(), selection(), availability())


@pytest.fixture
def context():
    service, request, transport = history_context()
    yield service, request, transport
    service.session.close()


def test_real_hourly_conversion_agrees_with_independent_daily_product():
    records, metadata = decoded()
    daily = json.loads((FIXTURES / "power-daily.json").read_bytes())
    totals = daily["properties"]["parameter"]["PRECTOTCORR"]
    assert metadata["raw_units"] == "mm/day"
    assert metadata["rate_multiplier_to_mm_h"] == 1 / 24
    assert len(records) == 72
    for day, depth in totals.items():
        actual = sum(r.value for r in records if r.interval_start.strftime("%Y%m%d") == day)
        # Provider rounds daily and hourly values to 0.01; not a hydraulic tolerance.
        assert actual == pytest.approx(depth, abs=0.006)
    assert records[0].support == "GRID_CELL_ESTIMATE"
    assert records[0].evidence_kind == "REANALYSIS"
    assert records[0].native_resolution_m == 65000


@pytest.mark.parametrize(
    "mutation",
    ["units", "timezone", "source", "location", "date", "duplicate", "outside", "geometry_nan"],
)
def test_provider_mismatch_rejected(mutation):
    raw = json.loads((FIXTURES / "power-hourly.json").read_bytes())
    if mutation == "units":
        raw["parameters"]["PRECTOTCORR"]["units"] = "unknown"
    elif mutation == "timezone":
        raw["header"]["time_standard"] = "LST"
    elif mutation == "source":
        raw["header"]["sources"] = ["GEOSIT"]
    elif mutation == "location":
        raw["geometry"]["coordinates"][0] += 1
    elif mutation == "geometry_nan":
        raw["geometry"]["coordinates"][0] = float("nan")
    elif mutation == "date":
        raw["header"]["start"] = "20210101"
    elif mutation == "outside":
        raw["properties"]["parameter"]["PRECTOTCORR"]["2021091800"] = 1
    payload = json.dumps(raw).encode()
    if mutation == "duplicate":
        payload = payload.replace(b'"2021091900":', b'"2021091900": 1, "2021091900":')
    with pytest.raises(ValueError):
        decode_power(payload, selection(), availability())


@pytest.mark.parametrize(
    "value,expected",
    [(None, "MISSING"), (-999, "MISSING"), (-1, "REJECTED"), (float("inf"), "REJECTED")],
)
def test_missing_and_rejected_values_never_become_dry(value, expected):
    raw = json.loads((FIXTURES / "power-hourly.json").read_bytes())
    raw["properties"]["parameter"]["PRECTOTCORR"]["2021091900"] = value
    records, _ = decode_power(json.dumps(raw).encode(), selection(), availability())
    assert records[0].value is None and records[0].qc == expected


def test_mm_hour_header_is_not_divided_again():
    raw = json.loads((FIXTURES / "power-hourly.json").read_bytes())
    raw["parameters"]["PRECTOTCORR"]["units"] = "mm/hour"
    records, _ = decode_power(json.dumps(raw).encode(), selection(), availability())
    assert records[0].value == 16.88


def test_no_lookahead_and_unknown_latency():
    r = decoded()[0][0]
    issue = r.interval_end
    assert not r.eligible_predictor(issue)
    assert not availability(
        availability_status="ESTIMATED", estimated_latency_seconds=3600
    ).eligible_at(issue)
    r.source = availability(availability_status="VERIFIED", provider_available_at=issue)
    assert r.eligible_predictor(issue)
    assert not r.eligible_predictor(issue - timedelta(seconds=1))
    r.source.provider_available_at = issue - timedelta(hours=1)
    assert not r.eligible_predictor(issue - timedelta(seconds=1))
    r.evidence_kind = "FORECAST"
    assert r.eligible_predictor(issue - timedelta(seconds=1))
    with pytest.raises(ValueError):
        availability(provider_available_at=issue)
    with pytest.raises(ValueError):
        availability(
            availability_status="VERIFIED",
            provider_available_at=issue,
            source_issue_time=issue + timedelta(hours=1),
        )


def test_timezone_interval_counter_and_station_projection():
    start, end = utc("2021-09-19T05:30+05:30"), utc("2021-09-19T06:00+05:30")
    assert start == utc("2021-09-19T00:00Z")
    assert rate_mm_h(10, "mm", start, end) == 20
    assert counter_increment(10, 13, "same", "same") == 3
    for previous, current, epoch in [(10, 1, "same"), (1, 10, "reset")]:
        with pytest.raises(ValueError, match="reset"):
            counter_increment(previous, current, "same", epoch)
    row = StationInterval(
        station_id="approved-file-test",
        x=640000,
        y=2500000,
        horizontal_crs="EPSG:32645",
        start=start,
        end=end,
        value=10,
        units="mm",
        qc="VALID",
        support_m=1,
        source=availability(),
    )
    record = normalize_stations([row, row])[0]
    assert record.value == 20 and record.support == "POINT"
    assert 88 < record.longitude < 89 and 22 < record.latitude < 23
    with pytest.raises(ValueError):
        StationInterval.model_validate(row.model_dump() | {"start": "2021-09-19T00:00"})
    with pytest.raises(ValueError):
        rate_mm_h(1, "mm", end, start)


def test_duplicates_corrections_and_level_reference():
    record = decoded()[0][0]
    assert deduplicate([record, record]) == [record]
    corrected = record.model_copy(deep=True)
    corrected.value += 1
    with pytest.raises(ValueError, match="conflicting duplicate"):
        deduplicate([record, corrected])
    corrected.source.dataset_version_id = uuid4()
    assert len(deduplicate([record, corrected])) == 2
    payload = record.model_dump() | {"quantity": "WATER_LEVEL", "units": "m", "value": -1}
    with pytest.raises(ValueError, match="reference"):
        ObservationRecord.model_validate(payload)
    assert ObservationRecord.model_validate(payload | {"vertical_reference": "datum-A"}).value == -1


def split_definition():
    return EvaluationDatasetDefinition(
        target_definition="catchment hourly rainfall mm/h",
        feature_definition="past-only inputs",
        label_quality="reanalysis estimate, no measured flood label",
        events=[
            {
                "historical_event_id": uuid4(),
                "storm_group": f"storm-{i}",
                "role": role,
                "start": f"202{i + 1}-09-19T00:00Z",
                "end": f"202{i + 1}-09-20T00:00Z",
                "geography": "test-catchment",
            }
            for i, role in enumerate(["TRAIN", "TUNE", "TEST"])
        ],
    )


@pytest.mark.parametrize("change", ["event", "group", "time", "cutoff"])
def test_whole_event_separation(change):
    split = split_definition()
    if change == "event":
        split.events[2].historical_event_id = split.events[0].historical_event_id
    elif change == "group":
        split.events[2].storm_group = split.events[0].storm_group
    elif change == "time":
        split.events[2].start = split.events[0].start
    else:
        split.base_model_training_cutoff = utc("2023-01-01T00:00Z")
    with pytest.raises(ValueError):
        EvaluationDatasetDefinition.model_validate_json(split.model_dump_json())


def test_split_hash_stable_and_sensitive():
    split = split_definition()
    assert (
        split.split_hash()
        == EvaluationDatasetDefinition.model_validate_json(split.model_dump_json()).split_hash()
    )
    digest = split.split_hash()
    split.target_definition = "different target"
    assert digest != split.split_hash()


def test_build_roundtrip_recreate_links_and_volume(context):
    service, request, _ = context
    event = service.build(request)
    assert service.build(request) == event
    assert len(event.windows) == 2
    assert all(w.end - w.start == timedelta(hours=3) for w in event.windows)
    for w in event.windows:
        assert w.blockers  # No invented stage or pump data.
        package = Manifest.model_validate_json(
            service.forcing.read_artifact(w.forcing_package_id, "manifest")
        )
        inputs = BuildRequest.model_validate_json(
            service.forcing.read_artifact(w.forcing_package_id, "request.json")
        )
        depth = sum(frame[0][0] for frame in inputs.forecast.rain.members[0].rain_rate_mm_h)
        volume = depth / 1000 * 120 * 80
        assert package.quality_summary.rainfall_volume_m3_by_member["reanalysis"] == pytest.approx(
            volume, rel=1e-12
        )
        assert inputs.antecedent is not None
        assert not package.quality_summary.hydraulic_use_eligible
    row = service.session.get(HistoricalEventRecord, event.historical_event_id)
    service.session.delete(row)
    service.session.commit()
    assert service.recreate(canonical_bytes(event.model_dump(mode="json"))) == event
    view = service.view(event.historical_event_id)
    assert view["coverage"] == {"valid": 6, "total": 6}
    assert len(view["intervals"]) == 6
    assert view["intervals"][-1]["accumulation_mm"] > 0


def test_missing_interval_omits_package_and_breaks_accumulation():
    service, request, _ = history_context(missing=True)
    try:
        event = service.build(request)
        assert event.windows[0].forcing_package_id is None
        assert event.windows[0].missing_intervals == 1
        assert event.windows[1].forcing_package_id is not None
        view = service.view(event.historical_event_id)
        assert view["coverage"]["valid"] == 5
        assert view["intervals"][-1]["accumulation_mm"] is None
    finally:
        service.session.close()


@pytest.mark.parametrize("kind", ["raw", "observations", "link", "metadata"])
def test_corruption_and_resigned_semantic_changes_fail(context, kind):
    service, request, _ = context
    event = service.build(request)
    if kind == "raw":
        service.forcing.store.raw_objects[event.raw_object.object_key] = b"changed"
    elif kind == "observations":
        ref = event.artifacts["observations.json"]
        service.forcing.store.spatial_objects[ref.object_key] = b"[]"
    elif kind == "link":
        event.windows[0].forcing_package_id, event.windows[1].forcing_package_id = (
            event.windows[1].forcing_package_id,
            event.windows[0].forcing_package_id,
        )
    else:
        event.title = "Different title"
    event.historical_event_id = identity(event)
    with pytest.raises(ValueError):
        service.validate(canonical_bytes(event.model_dump(mode="json")))


@pytest.mark.parametrize("kind", ["geometry", "time", "version", "object", "catchment"])
def test_request_overlap_and_raw_lineage_rejected(context, kind):
    service, request, _ = context
    if kind == "geometry":
        request.replay_grid.x_edges_m = [500000, 500100]
    elif kind == "time":
        request.event_end = request.selection.end + timedelta(hours=1)
    elif kind == "version":
        request.dataset_version_id = uuid4()
    elif kind == "catchment":
        request.catchment_id = "unrelated-area"
    else:
        request.raw_object_id = uuid4()
    with pytest.raises((ValueError, LookupError)):
        service.preview(request)


def test_resume_and_revoked_permission_do_not_download(context):
    service, request, transport = context
    registry = RegistryService(service.session)
    source = registry.get_source(source_definition(request.selection, request.city_id).source_id)
    transport.download = lambda *a, **k: pytest.fail("unexpected network request")
    reused = acquire_power(registry, service.harvester, request.selection)
    assert reused.dataset_version_id == request.dataset_version_id
    data = source.model_dump(exclude={"source_id", "created_at", "updated_at"})
    data.update(automation_allowed=False, access_class="UNKNOWN")
    registry.replace_source(source.source_id, SourceReplace.model_validate(data))
    with pytest.raises(PermissionError):
        acquire_power(registry, service.harvester, request.selection, refresh=True)


def test_preview_api_read_only_integrity_and_html_escaping(context):
    service, request, _ = context
    request.title = "</script><script>alert(1)</script>"
    event = service.build(request)
    app.dependency_overrides[get_history_service] = lambda: service
    try:
        client = TestClient(app)
        page = client.get("/history/preview")
        assert page.status_code == 200
        assert "not rain-gauge or radar measurements" in page.text
        assert client.get("/history/events").json()[0]["historical_event_id"] == str(
            event.historical_event_id
        )
        assert client.get(f"/history/events/{event.historical_event_id}/view").status_code == 200
        assert client.get(f"/history/events/{uuid4()}").status_code == 404
        html = render_preview(service.view(event.historical_event_id))
        assert "<script>alert(1)</script>" not in html
        assert "\\u003cscript\\u003e" in html
        # Reads cannot initiate operator jobs.
        assert not any(
            r.path.startswith("/history") and set(r.methods) - {"GET", "HEAD"}
            for r in app.routes
            if hasattr(r, "methods")
        )
        service.forcing.store.raw_objects[event.raw_object.object_key] = b"changed"
        assert client.get(f"/history/events/{event.historical_event_id}/view").status_code == 409
    finally:
        app.dependency_overrides.pop(get_history_service)


def test_retained_sequence10_bytes_and_identity_unchanged():
    raw = (FIXTURES / "sequence10-manifest.json").read_bytes()
    manifest = Manifest.model_validate_json(raw)
    assert manifest.forcing_package_id == UUID("e82ca9de-a4da-5ec1-b9cc-f097a8f1aa1c")
    assert forcing_identity(manifest)[0] == manifest.forcing_package_id
    request = (FIXTURES / "sequence10-request.json").read_bytes()
    assert sha256(request) == manifest.artifacts["request.json"].sha256
    assert (
        canonical_bytes(BuildRequest.model_validate_json(request).model_dump(mode="json"))
        == request
    )


def test_event_request_schema_extra_fields_rejected(context):
    _, request, _ = context
    with pytest.raises(ValueError):
        EventRequest.model_validate(request.model_dump() | {"measured_flood_validation": True})
