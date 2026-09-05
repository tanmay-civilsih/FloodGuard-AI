from __future__ import annotations

import hashlib
from io import BytesIO
from uuid import uuid4

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject

from floodguard.contracts.time import utc_now
from floodguard.harvester.contracts import (
    DatasetVersionRead,
    DatasetVersionStatus,
    RawObjectRead,
)
from floodguard.reconstruction.contracts import (
    CalibrationControlPoint,
    ReconstructionCalibration,
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


def synthetic_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=100, height=100)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    content = StreamObject()
    content.set_data(
        b"1 0 0 RG 1 w\n"
        b"10 20 m 22 20 l S\n24 20 m 36 20 l S\n38 20 m 55 20 l S\n"
        b"0 1 1 RG 46.9 30 m "
        b"46.9 33.81 43.81 36.9 40 36.9 c "
        b"36.19 36.9 33.1 33.81 33.1 30 c "
        b"33.1 26.19 36.19 23.1 40 23.1 c "
        b"43.81 23.1 46.9 26.19 46.9 30 c h S\n"
        b"BT /F1 5 Tf 1 0 0 1 42 24 Tm (MH 1) Tj ET\n"
        b"BT /F1 5 Tf 1 0 0 1 25 16 Tm (10m length sewer) Tj ET\n"
    )
    page[NameObject("/Contents")] = writer._add_object(content)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def source_and_version(
    payload: bytes,
) -> tuple[SourceRead, DatasetVersionRead, RawObjectRead, ReconstructionCalibration]:
    now = utc_now()
    source = SourceRead(
        source_id=uuid4(),
        provider="Municipal test authority",
        dataset_name="Synthetic drainage map",
        city_id="kolkata",
        category=SourceCategory.DRAINAGE_MAP,
        endpoint="https://example.test/synthetic.pdf",
        access_method=AccessMethod.HTTP,
        format="PDF",
        licence="Public domain test fixture",
        redistribution_policy="Test only",
        automation_allowed=True,
        access_class=AccessClass.OPEN_AUTOMATED,
        authentication_type=AuthenticationType.NONE,
        authority_level=AuthorityLevel.MUNICIPAL_PRIMARY,
        refresh_policy="Never",
        fallback_strategy="None",
        status=SourceStatus.AVAILABLE,
        created_at=now,
        updated_at=now,
    )
    version_id = uuid4()
    sha256 = hashlib.sha256(payload).hexdigest()
    raw_object = RawObjectRead(
        object_id=uuid4(),
        dataset_version_id=version_id,
        object_key="raw/kolkata/test/version/synthetic.pdf",
        filename="synthetic.pdf",
        source_url=source.endpoint,
        sha256=sha256,
        byte_size=len(payload),
        content_type="application/pdf",
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
        total_bytes=len(payload),
        previous_version_id=None,
        source_snapshot=source.model_dump(mode="json"),
        error_message=None,
        created_at=now,
        completed_at=now,
        objects=[raw_object],
    )
    controls = [
        CalibrationControlPoint(
            name=name,
            page_x=x,
            page_y=y,
            target_x=640_000.0 + x,
            target_y=2_500_000.0 + y,
            match_description=f"Synthetic control {name}",
        )
        for name, x, y in (
            ("southwest", 0.0, 0.0),
            ("southeast", 100.0, 0.0),
            ("northwest", 0.0, 100.0),
            ("northeast", 100.0, 100.0),
        )
    ]
    calibration = ReconstructionCalibration(
        calibration_id="synthetic-v1",
        ward_id="test",
        source_filename=raw_object.filename,
        source_sha256=sha256,
        source_page=1,
        target_crs="EPSG:32645",
        control_reference="Synthetic coordinate plane",
        control_reference_sha256="b" * 64,
        georeference_method="AFFINE_SYNTHETIC",
        max_georeference_rmse_m=0.001,
        control_points=controls,
    )
    return source, version, raw_object, calibration

