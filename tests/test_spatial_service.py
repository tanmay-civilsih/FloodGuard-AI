import hashlib
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from floodguard.contracts.time import utc_now
from floodguard.harvester.contracts import (
    DatasetVersionRead,
    DatasetVersionStatus,
    RawObjectRead,
)
from floodguard.registry.contracts import (
    AccessClass,
    AccessMethod,
    AuthenticationType,
    AuthorityLevel,
    SourceCategory,
    SourceRead,
    SourceStatus,
)
from floodguard.registry.models import Base
from floodguard.spatial.object_store import MemorySpatialObjectStore
from floodguard.spatial.repository import SpatialRepository
from floodguard.spatial.service import SpatialService

KML = b'''<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2">
<Document><Placemark><name>Layer</name><Polygon><outerBoundaryIs><LinearRing><coordinates>
88.35,22.55,0 88.36,22.55,0 88.36,22.56,0 88.35,22.56,0 88.35,22.55,0
</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>'''


def make_source(category: SourceCategory) -> SourceRead:
    now = utc_now()
    return SourceRead(
        source_id=uuid4(),
        provider="Test provider",
        dataset_name=f"Test {category.value}",
        city_id="kolkata",
        category=category,
        endpoint="https://example.test/layer.kml",
        access_method=AccessMethod.HTTP,
        format="KML",
        licence="Test licence",
        redistribution_policy="Attribute",
        automation_allowed=True,
        access_class=AccessClass.OPEN_AUTOMATED,
        authentication_type=AuthenticationType.NONE,
        authority_level=AuthorityLevel.COMMUNITY,
        refresh_policy="On demand",
        fallback_strategy="Use prior immutable version",
        status=SourceStatus.AVAILABLE,
        created_at=now,
        updated_at=now,
    )


def make_version(source: SourceRead, object_key: str) -> DatasetVersionRead:
    now = utc_now()
    version_id = uuid4()
    return DatasetVersionRead(
        dataset_version_id=version_id,
        dataset_id=uuid4(),
        source_id=source.source_id,
        city_id=source.city_id,
        acquired_at=now,
        status=DatasetVersionStatus.COMPLETE,
        manifest_sha256="a" * 64,
        manifest_object_key=f"{object_key}.manifest.json",
        object_count=1,
        total_bytes=len(KML),
        previous_version_id=None,
        source_snapshot=source.model_dump(mode="json"),
        error_message=None,
        created_at=now,
        completed_at=now,
        objects=[
            RawObjectRead(
                object_id=uuid4(),
                dataset_version_id=version_id,
                object_key=object_key,
                filename="layer.kml",
                source_url=source.endpoint,
                sha256=hashlib.sha256(KML).hexdigest(),
                byte_size=len(KML),
                content_type="application/vnd.google-earth.kml+xml",
                etag=None,
                last_modified=None,
                created_at=now,
            )
        ],
    )


def make_service(session: Session, store: MemorySpatialObjectStore) -> SpatialService:
    return SpatialService(
        SpatialRepository(session),
        store,
        working_crs="EPSG:32645",
        alignment_tolerance_m=0.05,
        rainfall_conservation_tolerance=1e-9,
        max_object_bytes=1024 * 1024,
    )


def test_normalization_is_idempotent_and_writes_separate_qa_artifact() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    source = make_source(SourceCategory.WARD_BOUNDARY)
    version = make_version(source, "raw/ward/layer.kml")
    store = MemorySpatialObjectStore(raw_objects={"raw/ward/layer.kml": KML})
    with Session(engine) as session:
        service = make_service(session, store)
        first = service.normalize_dataset(source, version)
        assert first.created_layers == 1
        assert first.reused_layers == 0
        assert len(store.spatial_objects) == 2

        second = service.normalize_dataset(source, version)
        assert second.created_layers == 0
        assert second.reused_layers == 1
        assert second.layer_ids == first.layer_ids
        assert len(store.spatial_objects) == 2

        layer = service.get_layer(first.layer_ids[0])
        assert layer.working_crs == "EPSG:32645"
        assert layer.max_roundtrip_error_m < 0.05
        assert b'"FeatureCollection"' in service.qa_geojson(layer.normalization_id)


def test_kolkata_readiness_requires_three_core_vector_categories() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    store = MemorySpatialObjectStore()
    with Session(engine) as session:
        service = make_service(session, store)
        for index, category in enumerate(
            [
                SourceCategory.WARD_BOUNDARY,
                SourceCategory.CATCHMENT,
                SourceCategory.WATER_BODY,
            ]
        ):
            source = make_source(category)
            object_key = f"raw/{index}/layer.kml"
            store.raw_objects[object_key] = KML
            service.normalize_dataset(source, make_version(source, object_key))

        readiness = service.readiness(city_id="kolkata")
        assert readiness.missing_core_categories == []
        assert readiness.alignment_check_passed is True
        assert readiness.vertical_metadata_valid is True
        assert readiness.rainfall_conservation.passed is True
