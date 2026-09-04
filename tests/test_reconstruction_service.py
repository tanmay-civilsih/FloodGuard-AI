import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from floodguard.reconstruction.contracts import (
    ReconstructionReviewCreate,
    ReconstructionStatus,
    ReviewDecision,
    ReviewerType,
)
from floodguard.reconstruction.repository import ReconstructionRepository
from floodguard.reconstruction.service import ReconstructionError, ReconstructionService
from floodguard.registry.models import Base
from floodguard.spatial.object_store import MemorySpatialObjectStore
from tests.reconstruction_fixtures import source_and_version, synthetic_pdf


def test_reconstruction_is_idempotent_traceable_and_human_gated() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    payload = synthetic_pdf()
    source, version, raw_object, calibration = source_and_version(payload)
    store = MemorySpatialObjectStore(raw_objects={raw_object.object_key: payload})
    with Session(engine) as session:
        service = ReconstructionService(
            ReconstructionRepository(session),
            store,
            working_crs="EPSG:32645",
            max_object_bytes=1024 * 1024,
        )
        first = service.reconstruct(source, version, raw_object, calibration)
        assert first.created is True
        assert first.status is ReconstructionStatus.PENDING_REVIEW
        assert first.drain_count == 1
        assert first.structure_count == 1
        assert first.label_count == 2
        assert first.georeference_rmse_m < 1e-6
        assert len(store.spatial_objects) == 3

        second = service.reconstruct(source, version, raw_object, calibration)
        assert second.created is False
        assert second.reconstruction_id == first.reconstruction_id
        assert len(store.spatial_objects) == 3

        record = service.get(first.reconstruction_id)
        assert record.source_sha256 == raw_object.sha256
        assert record.native_inspection.ocr_used is False
        qa = json.loads(service.qa_geojson(first.reconstruction_id))
        drain = next(
            feature
            for feature in qa["features"]
            if feature["properties"]["feature_kind"] == "DRAIN"
        )
        assert drain["properties"]["dimension_m"] is None
        assert drain["properties"]["invert_elevation_m"] is None
        assert drain["properties"]["flow_direction"] is None
        assert drain["properties"]["material"] is None
        assert service.readiness(city_id="kolkata").completion_gate_passed is False

        automated_approval = ReconstructionReviewCreate(
            decision=ReviewDecision.APPROVE,
            reviewer="Automated test agent",
            reviewer_type=ReviewerType.AUTOMATED,
            notes="Automated visual checks passed.",
            source_alignment_checked=True,
            drain_symbology_checked=True,
            feature_placement_checked=True,
            missing_attributes_not_invented=True,
        )
        with pytest.raises(ReconstructionError, match="human approval"):
            service.review(first.reconstruction_id, automated_approval)

        human_approval = automated_approval.model_copy(
            update={
                "reviewer": "Test municipal engineer",
                "reviewer_type": ReviewerType.HUMAN,
                "notes": "Synthetic QA fixture inspected for all four checks.",
            }
        )
        review = service.review(first.reconstruction_id, human_approval)
        assert review.reviewer_type is ReviewerType.HUMAN
        assert service.get(first.reconstruction_id).status is ReconstructionStatus.APPROVED
        assert service.readiness(city_id="kolkata").completion_gate_passed is True

