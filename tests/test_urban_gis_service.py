import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from floodguard.registry.models import Base
from floodguard.spatial.object_store import MemorySpatialObjectStore
from floodguard.urban_gis.repository import UrbanGisRepository
from floodguard.urban_gis.service import UrbanGisError, UrbanGisService
from tests.test_urban_gis_contracts import package


def build_service() -> tuple[UrbanGisService, Session, MemorySpatialObjectStore]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    store = MemorySpatialObjectStore()
    return UrbanGisService(
        UrbanGisRepository(session),
        store,
        working_crs="EPSG:32645",
    ), session, store


def test_build_is_immutable_separate_and_hash_verified() -> None:
    service, session, _ = build_service()
    try:
        created = service.build(package())
        reused = service.build(package())
        assert created.created is True
        assert reused.created is False
        assert reused.urban_gis_id == created.urban_gis_id

        visual = json.loads(service.read_artifact(created.urban_gis_id, "visual"))
        hydraulic = json.loads(service.read_artifact(created.urban_gis_id, "hydraulic"))
        roof = json.loads(service.read_artifact(created.urban_gis_id, "roof-runoff"))
        assert visual != hydraulic
        assert hydraulic["features"][0]["properties"]["hydraulic_domain"] == "SURFACE_2D"
        assert roof["surface_cell_binding"] == "DEFERRED_TO_LATER_SEQUENCE"

        readiness = service.readiness(city_id="kolkata")
        assert readiness.technical_development_gate_passed is True
        assert readiness.final_human_acceptance_pending is True
        assert readiness.final_completion_gate_passed is False
    finally:
        session.close()


def test_artifact_corruption_fails_closed() -> None:
    service, session, store = build_service()
    try:
        result = service.build(package())
        record = service.repository.get(result.urban_gis_id)
        assert record is not None
        store.spatial_objects[record.hydraulic_object_key] = b"{}"
        with pytest.raises(UrbanGisError, match="SHA-256"):
            service.read_artifact(result.urban_gis_id, "hydraulic")
    finally:
        session.close()


def test_configured_working_crs_must_match_package() -> None:
    service, session, _ = build_service()
    try:
        data = package().model_dump()
        data["working_crs"] = "EPSG:32644"
        with pytest.raises(UrbanGisError, match="configured working CRS"):
            service.build(package().model_validate(data))
    finally:
        session.close()
