import pytest
from pydantic import ValidationError

from floodguard.urban_gis.contracts import (
    HydraulicFeature,
    RoofReceivingGeometry,
    RoofRunoffRule,
    SurfaceHydrologyPolicy,
    UrbanGisPackage,
    VisualFeature,
)


def polygon(
    x0: float = 0.0, y0: float = 0.0, x1: float = 10.0, y1: float = 10.0,
) -> dict[str, object]:
    return {
        "type": "Polygon",
        "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
    }


def simple_policy() -> SurfaceHydrologyPolicy:
    return SurfaceHydrologyPolicy(
        loss_mode="SIMPLIFIED_RUNOFF",
        parameter_status="ASSUMED",
        source_reference="fixture://surface-policy",
        runoff_coefficient=0.9,
    )


def package() -> UrbanGisPackage:
    return UrbanGisPackage(
        city_id="kolkata",
        pilot_area_id="kolkata-sequence7-reference",
        working_crs="EPSG:32645",
        evidence_scope="REFERENCE_FIXTURE",
        source_references=["fixture://sequence7"],
        visual_features=[
            VisualFeature(
                feature_id="building-1",
                visual_class="BUILDING",
                geometry=polygon(),
                source_reference="fixture://building-1",
                height_m=9.0,
            )
        ],
        hydraulic_features=[
            HydraulicFeature(
                feature_id="roof-1",
                surface_class="ROOF",
                hydraulic_domain="SURFACE_2D",
                geometry=polygon(),
                source_reference="fixture://roof-1",
                hydrology=simple_policy(),
            )
        ],
        roof_runoff_rules=[
            RoofRunoffRule(
                roof_feature_id="roof-1",
                target_kind="RECEIVING_GEOMETRY",
                receiving_geometry=RoofReceivingGeometry(
                    receiving_geometry_id="roof-1-ground",
                    version=1,
                    geometry=polygon(10.0, 0.0, 20.0, 10.0),
                    source_reference="fixture://roof-1-ground",
                ),
                target_source_reference="fixture://roof-1-ground",
            )
        ],
        limitations=["Reference fixture only; this is not real-pilot engineering evidence."],
    )


def test_valid_package_has_versioned_receiving_geometry() -> None:
    result = package()
    assert result.roof_runoff_rules[0].receiving_geometry is not None
    assert result.roof_runoff_rules[0].receiving_geometry.version == 1


def test_roof_requires_exactly_one_rule() -> None:
    data = package().model_dump()
    data["roof_runoff_rules"] = []
    with pytest.raises(ValidationError, match="roof runoff rules"):
        UrbanGisPackage.model_validate(data)


def test_surface_cell_ids_are_forbidden_in_sequence7() -> None:
    data = package().model_dump()
    data["roof_runoff_rules"][0]["surface_cell_ids"] = ["cell-1"]
    with pytest.raises(ValidationError):
        UrbanGisPackage.model_validate(data)


def test_surface_feature_cannot_claim_network_ownership() -> None:
    data = package().model_dump()
    data["hydraulic_features"][0]["hydraulic_domain"] = "NETWORK_1D"
    with pytest.raises(ValidationError, match="NETWORK_1D"):
        UrbanGisPackage.model_validate(data)


def test_loss_modes_are_mutually_exclusive() -> None:
    with pytest.raises(ValidationError, match="explicit losses"):
        SurfaceHydrologyPolicy(
            loss_mode="SIMPLIFIED_RUNOFF",
            parameter_status="ASSUMED",
            source_reference="fixture://bad-policy",
            runoff_coefficient=0.8,
            infiltration_rate_mm_h=2.0,
        )
