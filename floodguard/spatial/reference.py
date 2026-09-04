"""Horizontal and vertical reference-system validation for Sequence 4."""

from __future__ import annotations

from pyproj import CRS

from floodguard.spatial.contracts import (
    DatumTransformStatus,
    SpatialVariableKind,
    VerticalReference,
)


class ReferenceSystemError(ValueError):
    pass


def validate_metric_working_crs(value: str) -> CRS:
    crs = CRS.from_user_input(value)
    if not crs.is_projected:
        raise ReferenceSystemError("working CRS must be projected")
    axis_units = {axis.unit_name.lower() for axis in crs.axis_info if axis.unit_name}
    if not axis_units or not axis_units.issubset({"metre", "meter"}):
        raise ReferenceSystemError("working CRS axes must use metres")
    return crs


def validate_vertical_reference(
    variable_kind: SpatialVariableKind,
    reference: VerticalReference,
) -> VerticalReference:
    if variable_kind is not SpatialVariableKind.ELEVATION:
        return reference
    if reference.vertical_datum is None:
        raise ReferenceSystemError("elevation data require vertical_datum")
    if reference.vertical_unit is None:
        raise ReferenceSystemError("elevation data require vertical_unit")
    if reference.vertical_unit.lower() not in {"m", "metre", "meter", "metres", "meters"}:
        raise ReferenceSystemError("Sequence 4 internal elevation unit must be metres")
    if reference.datum_transform_status in {
        DatumTransformStatus.NOT_APPLICABLE,
        DatumTransformStatus.UNRESOLVED,
    }:
        raise ReferenceSystemError(
            "elevation data require a compatible or explicitly transformed vertical reference"
        )
    return reference
