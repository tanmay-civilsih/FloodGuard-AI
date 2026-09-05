import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from floodguard.registry.models import Base
from floodguard.spatial.object_store import MemorySpatialObjectStore
from floodguard.terrain.contracts import TerrainPackage, TerrainReadinessStatus, VerticalQuality
from floodguard.terrain.grid import package_bytes
from floodguard.terrain.repository import TerrainRepository
from floodguard.terrain.service import (
    TerrainConditioningError,
    TerrainService,
    _readiness_status,
)
from tests.terrain_fixtures import source_and_version, synthetic_package


def _service(raw_object_key: str, payload: bytes) -> tuple[TerrainService, Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    store = MemorySpatialObjectStore(raw_objects={raw_object_key: payload})
    return (
        TerrainService(
            TerrainRepository(session),
            store,
            working_crs="EPSG:32645",
            max_object_bytes=1024 * 1024,
        ),
        session,
    )


def test_build_is_immutable_idempotent_and_exposes_all_products() -> None:
    source, version, raw_object, payload = source_and_version()
    service, session = _service(raw_object.object_key, payload)
    try:
        created = service.build_from_raw(source, version, raw_object)
        reused = service.build_from_raw(source, version, raw_object)

        assert created.created is True
        assert reused.created is False
        assert reused.terrain_id == created.terrain_id
        assert created.readiness_status is TerrainReadinessStatus.HYDRAULIC_SCENARIO_READY

        record = service.get(created.terrain_id)
        assert record.source_surface_type.value == "DSM"
        assert record.native_horizontal_resolution_m == 30.0
        assert record.computational_resolution_m == 10.0
        assert record.effective_information_resolution_m == 30.0
        assert record.validation_limitations

        raw = service.read_artifact(created.terrain_id, "RAW_ELEVATION")
        visual = json.loads(
            service.read_artifact(created.terrain_id, "VISUAL_TERRAIN").decode("utf-8")
        )
        hydraulic = json.loads(
            service.read_artifact(created.terrain_id, "HYDRAULIC_TERRAIN").decode("utf-8")
        )
        structure = json.loads(
            service.read_artifact(created.terrain_id, "MULTI_LEVEL_STRUCTURE_CATALOG").decode(
                "utf-8"
            )
        )
        qa = json.loads(service.read_artifact(created.terrain_id, "QA").decode("utf-8"))
        assert raw == payload
        assert visual["product"] == "VISUAL_TERRAIN"
        assert hydraulic["product"] == "HYDRAULIC_TERRAIN"
        assert visual["grid"]["elevations_m"] != hydraulic["grid"]["elevations_m"]
        assert hydraulic["grid"]["elevations_m"][2][2] == 90.0
        assert structure["structures"][0]["kind"] == "UNDERPASS"
        assert qa["type"] == "FeatureCollection"
        assert any(
            feature["properties"]["feature_kind"] == "MULTI_LEVEL_STRUCTURE"
            for feature in qa["features"]
        )

        readiness = service.readiness(city_id="kolkata")
        assert readiness.total_terrains == 1
        assert readiness.hydraulic_scenario_ready == 1
        assert readiness.completion_gate_passed is True
    finally:
        session.close()


def test_terrain_requires_metric_grid_and_manifest_integrity() -> None:
    package = synthetic_package().model_copy(
        update={
            "grid": synthetic_package().grid.model_copy(update={"crs": "EPSG:4326"}),
        }
    )
    payload = package_bytes(package)
    source, version, raw_object, _ = source_and_version(payload)
    service, session = _service(raw_object.object_key, payload)
    try:
        with pytest.raises(TerrainConditioningError, match="metric working CRS"):
            service.build_from_raw(source, version, raw_object)
    finally:
        session.close()

    source, version, raw_object, payload = source_and_version()
    bad_object = raw_object.model_copy(update={"sha256": "f" * 64})
    service, session = _service(bad_object.object_key, payload)
    try:
        with pytest.raises(TerrainConditioningError, match="immutable manifest"):
            service.build_from_raw(source, version, bad_object)
    finally:
        session.close()


def test_unknown_vertical_reference_stays_visual_ready() -> None:
    package = synthetic_package().model_copy(
        update={
            "vertical_quality": VerticalQuality.UNKNOWN,
            "vertical_datum": None,
            "vertical_unit": None,
        }
    )
    payload = package_bytes(package)
    source, version, raw_object, _ = source_and_version(payload)
    service, session = _service(raw_object.object_key, payload)
    try:
        result = service.build_from_raw(source, version, raw_object)
        assert result.readiness_status is TerrainReadinessStatus.VISUAL_READY
        readiness = service.readiness(city_id="kolkata")
        assert readiness.completion_gate_passed is False
        assert readiness.visual_ready == 1
    finally:
        session.close()


def test_summary_metrics_cannot_claim_hydraulic_validation() -> None:
    data = synthetic_package().model_dump()
    data["vertical_validation"].update(
        method="claimed survey", rmse_m=0.1, control_point_count=100,
        road_sag_validation="PASSED", underpass_validation="PASSED",
        drain_rim_elevation_consistency="NOT_APPLICABLE",
    )
    assert _readiness_status(TerrainPackage.model_validate(data)) is (
        TerrainReadinessStatus.HYDRAULIC_SCENARIO_READY
    )


@pytest.mark.parametrize(
    "validation",
    [
        {"road_sag_validation": "FAILED"},
        {"underpass_validation": "FAILED"},
        {"drain_rim_elevation_consistency": "FAILED"},
        {"rmse_m": 6, "control_point_count": 3},
    ],
)
def test_failed_validation_is_not_scenario_ready(validation) -> None:
    data = synthetic_package().model_dump()
    data["vertical_validation"].update(validation)
    assert _readiness_status(TerrainPackage.model_validate(data)) is (
        TerrainReadinessStatus.VISUAL_READY
    )


def test_transform_label_without_evidence_is_not_scenario_ready() -> None:
    data = synthetic_package().model_dump()
    data["datum_transform_status"] = "TRANSFORMED"
    assert _readiness_status(TerrainPackage.model_validate(data)) is (
        TerrainReadinessStatus.VISUAL_READY
    )


def test_old_pipeline_cannot_satisfy_current_gate() -> None:
    source, version, raw_object, payload = source_and_version()
    service, session = _service(raw_object.object_key, payload)
    try:
        result = service.build_from_raw(source, version, raw_object)
        record = service.repository.get(result.terrain_id)
        assert record is not None
        record.pipeline_version = "sequence-6-terrain-v1"
        record.readiness_status = "HYDRAULIC_VALIDATED"
        session.commit()
        readiness = service.readiness(city_id="kolkata")
        assert not readiness.completion_gate_passed
        assert readiness.best_readiness_status is TerrainReadinessStatus.NOT_READY
        assert readiness.eligible_terrains == 0
        assert readiness.historical_terrains == readiness.total_terrains == 1
        assert service.get(result.terrain_id).pipeline_version == "sequence-6-terrain-v1"
    finally:
        session.close()


def test_unlisted_raw_object_is_rejected() -> None:
    source, version, raw_object, payload = source_and_version()
    service, session = _service(raw_object.object_key, payload)
    try:
        with pytest.raises(TerrainConditioningError, match="immutable manifest entry"):
            service.build_from_raw(source, version.model_copy(update={"objects": []}), raw_object)
    finally:
        session.close()


def test_new_failed_pilot_product_supersedes_earlier_scenario_ready_product() -> None:
    source, version, raw_object, payload = source_and_version()
    service, session = _service(raw_object.object_key, payload)
    try:
        service.build_from_raw(source, version, raw_object)
        data = synthetic_package().model_dump()
        data["vertical_validation"]["underpass_validation"] = "FAILED"
        new_payload = package_bytes(TerrainPackage.model_validate(data))
        new_source, new_version, new_object, _ = source_and_version(new_payload)
        # Replacing a store is confined to this test; real raw objects remain immutable.
        service.object_store = MemorySpatialObjectStore(
            raw_objects={new_object.object_key: new_payload}
        )
        service.build_from_raw(new_source, new_version, new_object)
        readiness = service.readiness(city_id="kolkata")
        assert readiness.total_terrains == 2
        assert readiness.eligible_terrains == readiness.historical_terrains == 1
        assert readiness.visual_ready == 1
        assert not readiness.completion_gate_passed
    finally:
        session.close()
