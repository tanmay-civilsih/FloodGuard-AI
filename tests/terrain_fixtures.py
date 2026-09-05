from __future__ import annotations

import hashlib
from uuid import uuid4

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
from floodguard.spatial.contracts import DatumTransformStatus
from floodguard.terrain.contracts import (
    AssessmentStatus,
    MultiLevelStructure,
    MultiLevelStructureKind,
    SurfaceType,
    TerrainGrid,
    TerrainIntervention,
    TerrainInterventionKind,
    TerrainPackage,
    VerticalQuality,
    VerticalValidation,
)
from floodguard.terrain.grid import package_bytes


def synthetic_package() -> TerrainPackage:
    elevations = [
        [100.0, 100.0, 100.0, 100.0, 100.0],
        [100.0, 101.0, 101.0, 100.0, 100.0],
        [100.0, 100.0, 90.0, 100.0, 100.0],
        [100.0, 100.0, 100.0, 100.0, 100.0],
    ]
    return TerrainPackage(
        pilot_area_id="kolkata-ward-7-test",
        grid=TerrainGrid(
            width=5,
            height=4,
            origin_x_m=300_000.0,
            origin_y_m=2_500_000.0,
            cell_size_m=10.0,
            crs="EPSG:32645",
            elevations_m=elevations,
        ),
        source_surface_type=SurfaceType.DSM,
        vertical_datum="EGM2008",
        vertical_unit="m",
        datum_transform_status=DatumTransformStatus.COMPATIBLE,
        vertical_quality=VerticalQuality.COARSE_GLOBAL_DEM,
        native_horizontal_resolution_m=30.0,
        computational_resolution_m=10.0,
        effective_information_resolution_m=30.0,
        depression_assessment=AssessmentStatus.CATALOGUED,
        multi_level_assessment=AssessmentStatus.CATALOGUED,
        interventions=[
            TerrainIntervention(
                row=2,
                column=2,
                kind=TerrainInterventionKind.PRESERVE_DEPRESSION,
                source_reference="survey://underpass-01",
                reason="Observed road sag is flood-relevant storage and must remain lower.",
            ),
            TerrainIntervention(
                row=0,
                column=0,
                kind=TerrainInterventionKind.FILL_DOCUMENTED_ARTIFACT,
                target_elevation_m=101.0,
                source_reference="qa://cell-0-0",
                reason="Single-cell spike is a documented source artifact.",
            ),
            TerrainIntervention(
                row=1,
                column=1,
                kind=TerrainInterventionKind.REMOVE_DOCUMENTED_OBSTRUCTION,
                target_elevation_m=99.0,
                source_reference="qa://building-footprint-01",
                reason="Mapped obstruction must not block the hydraulic surface.",
            ),
        ],
        multi_level_structures=[
            MultiLevelStructure(
                structure_id="underpass-01",
                kind=MultiLevelStructureKind.UNDERPASS,
                bounds_working=[300_000.0, 2_500_000.0, 300_040.0, 2_500_020.0],
                lower_elevation_m=95.0,
                upper_elevation_m=103.0,
                upper_level_role="elevated_road",
                lower_level_role="underpass_carriageway",
                source_reference="survey://underpass-01",
                confidence=0.82,
            )
        ],
        vertical_validation=VerticalValidation(
            limitations=["No control survey is available in the synthetic package."],
        ),
        limitations=[
            "Synthetic fixture; source is a coarse DSM and has no control survey.",
            "Hydraulic readiness is scenario-ready only until vertical validation is supplied.",
        ],
    )


def source_and_version(
    payload: bytes | None = None,
) -> tuple[SourceRead, DatasetVersionRead, RawObjectRead, bytes]:
    package = synthetic_package()
    raw_payload = payload or package_bytes(package)
    now = utc_now()
    source = SourceRead(
        source_id=uuid4(),
        provider="Synthetic elevation authority",
        dataset_name="Synthetic metric terrain package",
        city_id="kolkata",
        category=SourceCategory.ELEVATION,
        endpoint="https://example.test/synthetic.terrain.json",
        access_method=AccessMethod.HTTP,
        format="JSON TerrainPackage",
        licence="Public domain test fixture",
        redistribution_policy="Test only",
        automation_allowed=True,
        access_class=AccessClass.OPEN_AUTOMATED,
        authentication_type=AuthenticationType.NONE,
        authority_level=AuthorityLevel.NATIONAL_GOVERNMENT,
        horizontal_crs="EPSG:32645",
        vertical_datum="EGM2008",
        spatial_resolution="30 m native",
        temporal_resolution="Static",
        refresh_policy="Never",
        fallback_strategy="None",
        status=SourceStatus.AVAILABLE,
        created_at=now,
        updated_at=now,
    )
    version_id = uuid4()
    source_object = RawObjectRead(
        object_id=uuid4(),
        dataset_version_id=version_id,
        object_key="raw/kolkata/test/version/synthetic.terrain.json",
        filename="synthetic.terrain.json",
        source_url=source.endpoint,
        sha256=hashlib.sha256(raw_payload).hexdigest(),
        byte_size=len(raw_payload),
        content_type="application/json",
        etag=None,
        last_modified=None,
        created_at=now,
    )
    version = DatasetVersionRead(
        dataset_version_id=version_id,
        dataset_id=uuid4(),
        source_id=source.source_id,
        city_id=source.city_id,
        acquired_at=now,
        status=DatasetVersionStatus.COMPLETE,
        manifest_sha256="a" * 64,
        manifest_object_key="raw/manifest.json",
        object_count=1,
        total_bytes=len(raw_payload),
        previous_version_id=None,
        source_snapshot=source.model_dump(mode="json"),
        error_message=None,
        created_at=now,
        completed_at=now,
        objects=[source_object],
    )
    return source, version, source_object, raw_payload
