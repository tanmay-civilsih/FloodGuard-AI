"""Deterministic Sequence 7 reference fixture; never real-pilot evidence."""

from __future__ import annotations

from typing import Any

from floodguard.urban_gis.contracts import (
    EngineeringValueStatus,
    HydraulicDomain,
    HydraulicFeature,
    HydraulicSurfaceClass,
    HydrologicLossMode,
    RoofReceivingGeometry,
    RoofRunoffRule,
    RoofRunoffTargetKind,
    SurfaceHydrologyPolicy,
    UrbanGisEvidenceScope,
    UrbanGisPackage,
    VisualFeature,
    VisualFeatureClass,
)


def _polygon(x0: float, y0: float, x1: float, y1: float) -> dict[str, Any]:
    return {
        "type": "Polygon",
        "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
    }


def _simple(coefficient: float, name: str) -> SurfaceHydrologyPolicy:
    return SurfaceHydrologyPolicy(
        loss_mode=HydrologicLossMode.SIMPLIFIED_RUNOFF,
        parameter_status=EngineeringValueStatus.ASSUMED,
        source_reference=f"reference-fixture://{name}",
        runoff_coefficient=coefficient,
    )


def _explicit(infiltration: float, loss: float, name: str) -> SurfaceHydrologyPolicy:
    return SurfaceHydrologyPolicy(
        loss_mode=HydrologicLossMode.EXPLICIT_LOSS,
        parameter_status=EngineeringValueStatus.ASSUMED,
        source_reference=f"reference-fixture://{name}",
        infiltration_rate_mm_h=infiltration,
        other_loss_rate_mm_h=loss,
    )


def reference_package(
    *,
    city_id: str = "kolkata",
    pilot_area_id: str = "kolkata-sequence7-reference",
    working_crs: str = "EPSG:32645",
) -> UrbanGisPackage:
    """Create controlled geometry that exercises every Sequence 7 surface class."""
    x = 300_000.0
    y = 2_500_000.0
    visual = [
        VisualFeature(
            feature_id="visual-building",
            visual_class=VisualFeatureClass.BUILDING,
            geometry=_polygon(x, y, x + 20, y + 20),
            source_reference="reference-fixture://building",
            height_m=12.0,
        ),
        VisualFeature(
            feature_id="visual-road",
            visual_class=VisualFeatureClass.ROAD,
            geometry=_polygon(x + 25, y, x + 65, y + 10),
            source_reference="reference-fixture://road",
        ),
        VisualFeature(
            feature_id="visual-water",
            visual_class=VisualFeatureClass.WATER_BODY,
            geometry=_polygon(x, y + 30, x + 30, y + 50),
            source_reference="reference-fixture://water",
        ),
        VisualFeature(
            feature_id="visual-park",
            visual_class=VisualFeatureClass.PARK,
            geometry=_polygon(x + 40, y + 30, x + 70, y + 55),
            source_reference="reference-fixture://park",
        ),
    ]
    hydraulic = [
        HydraulicFeature(
            feature_id="road-1",
            surface_class=HydraulicSurfaceClass.ROAD,
            hydraulic_domain=HydraulicDomain.SURFACE_2D,
            geometry=_polygon(x + 25, y, x + 65, y + 10),
            source_reference="reference-fixture://road",
            hydrology=_simple(0.90, "road-policy"),
        ),
        HydraulicFeature(
            feature_id="roof-1",
            surface_class=HydraulicSurfaceClass.ROOF,
            hydraulic_domain=HydraulicDomain.SURFACE_2D,
            geometry=_polygon(x, y, x + 20, y + 20),
            source_reference="reference-fixture://roof",
            hydrology=_simple(0.95, "roof-policy"),
        ),
        HydraulicFeature(
            feature_id="barrier-1",
            surface_class=HydraulicSurfaceClass.BUILDING_BARRIER,
            hydraulic_domain=HydraulicDomain.SURFACE_2D,
            geometry=_polygon(x, y, x + 20, y + 20),
            source_reference="reference-fixture://barrier",
        ),
        HydraulicFeature(
            feature_id="soil-1",
            surface_class=HydraulicSurfaceClass.OPEN_SOIL,
            hydraulic_domain=HydraulicDomain.SURFACE_2D,
            geometry=_polygon(x + 75, y, x + 95, y + 20),
            source_reference="reference-fixture://soil",
            hydrology=_explicit(5.0, 1.0, "soil-policy"),
        ),
        HydraulicFeature(
            feature_id="park-1",
            surface_class=HydraulicSurfaceClass.PARK,
            hydraulic_domain=HydraulicDomain.SURFACE_2D,
            geometry=_polygon(x + 40, y + 30, x + 70, y + 55),
            source_reference="reference-fixture://park",
            hydrology=_explicit(4.0, 1.0, "park-policy"),
        ),
        HydraulicFeature(
            feature_id="water-1",
            surface_class=HydraulicSurfaceClass.WATER,
            hydraulic_domain=HydraulicDomain.SURFACE_2D,
            geometry=_polygon(x, y + 30, x + 30, y + 50),
            source_reference="reference-fixture://water",
        ),
        HydraulicFeature(
            feature_id="rail-1",
            surface_class=HydraulicSurfaceClass.RAILWAY,
            hydraulic_domain=HydraulicDomain.SURFACE_2D,
            geometry=_polygon(x + 75, y + 30, x + 100, y + 37),
            source_reference="reference-fixture://rail",
            hydrology=_simple(0.70, "rail-policy"),
        ),
        HydraulicFeature(
            feature_id="impervious-1",
            surface_class=HydraulicSurfaceClass.OTHER_IMPERVIOUS,
            hydraulic_domain=HydraulicDomain.SURFACE_2D,
            geometry=_polygon(x + 75, y + 45, x + 95, y + 60),
            source_reference="reference-fixture://impervious",
            hydrology=_simple(0.85, "impervious-policy"),
        ),
    ]
    rules = [
        RoofRunoffRule(
            roof_feature_id="roof-1",
            target_kind=RoofRunoffTargetKind.RECEIVING_GEOMETRY,
            receiving_geometry=RoofReceivingGeometry(
                receiving_geometry_id="roof-1-ground-v1",
                version=1,
                geometry=_polygon(x + 20, y, x + 25, y + 20),
                source_reference="reference-fixture://roof-receiver",
            ),
            target_source_reference="reference-fixture://roof-receiver",
        )
    ]
    return UrbanGisPackage(
        city_id=city_id,
        pilot_area_id=pilot_area_id,
        working_crs=working_crs,
        evidence_scope=UrbanGisEvidenceScope.REFERENCE_FIXTURE,
        source_references=["reference-fixture://sequence7-controlled-geometry"],
        visual_features=visual,
        hydraulic_features=hydraulic,
        roof_runoff_rules=rules,
        limitations=[
            "Controlled synthetic geometry for automated Sequence 7 development validation only; "
            "not Ward 7 engineering evidence."
        ],
    )
