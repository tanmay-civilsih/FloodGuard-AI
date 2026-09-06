"""Database/memory-vault integration regressions for the full pinned-runtime suite."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from floodguard.registry.contracts import SourceCategory
from floodguard.registry.models import Base
from floodguard.spatial.object_store import MemorySpatialObjectStore
from floodguard.spatial.service import SpatialNormalizationError
from tests.test_spatial_service import KML, make_service, make_source, make_version


@pytest.mark.parametrize("phase", ["before_first_build", "after_existing_build"])
def test_raw_manifest_verification_cannot_be_bypassed_by_reuse(phase: str) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    store = MemorySpatialObjectStore(raw_objects={"raw/ward": KML})
    source = make_source(SourceCategory.WARD_BOUNDARY)
    version = make_version(source, "raw/ward")
    with Session(engine) as session:
        service = make_service(session, store)
        if phase == "after_existing_build":
            service.normalize_dataset(source, version)
        store.raw_objects["raw/ward"] = KML.replace(b"88.35", b"88.45")
        with pytest.raises(SpatialNormalizationError, match="SHA-256"):
            service.normalize_dataset(source, version)


def test_qa_tampering_removes_current_eligibility() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    store = MemorySpatialObjectStore(raw_objects={"raw/ward": KML})
    source = make_source(SourceCategory.WARD_BOUNDARY)
    with Session(engine) as session:
        service = make_service(session, store)
        result = service.normalize_dataset(source, make_version(source, "raw/ward"))
        layer = service.get_layer(result.layer_ids[0])
        assert service.readiness(city_id="kolkata").eligible_layers == 1
        store.spatial_objects[layer.qa_object_key] += b" "
        with pytest.raises(SpatialNormalizationError):
            service.qa_geojson(layer.normalization_id)
        readiness = service.readiness(city_id="kolkata")
        assert readiness.eligible_layers == 0
        assert readiness.cross_layer_alignment_status == "NOT_ASSESSED"
        assert readiness.elevation_metadata_status == "NOT_APPLICABLE_NO_ELEVATION"
        assert readiness.rainfall_conservation_scope == "SYNTHETIC_SELF_TEST"
