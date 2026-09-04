import pytest

from floodguard.spatial.contracts import (
    DatumTransformStatus,
    SpatialVariableKind,
    VerticalReference,
    VerticalReferenceConfidence,
)
from floodguard.spatial.reference import (
    ReferenceSystemError,
    validate_metric_working_crs,
    validate_vertical_reference,
)


def test_kolkata_working_crs_is_projected_metric() -> None:
    crs = validate_metric_working_crs("EPSG:32645")
    assert crs.is_projected is True


def test_geographic_working_crs_is_rejected() -> None:
    with pytest.raises(ReferenceSystemError):
        validate_metric_working_crs("EPSG:4326")


def test_elevation_requires_explicit_vertical_reference() -> None:
    with pytest.raises(ReferenceSystemError):
        validate_vertical_reference(
            SpatialVariableKind.ELEVATION,
            VerticalReference(datum_transform_status=DatumTransformStatus.UNRESOLVED),
        )

    valid = VerticalReference(
        vertical_datum="TEST_VERTICAL_DATUM",
        vertical_unit="m",
        vertical_offset_m=0.0,
        datum_transform_status=DatumTransformStatus.TRANSFORMED,
        vertical_reference_confidence=VerticalReferenceConfidence.HIGH,
        transform_method="Validated test transform",
    )
    assert validate_vertical_reference(SpatialVariableKind.ELEVATION, valid) == valid
