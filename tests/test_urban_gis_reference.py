from floodguard.urban_gis.contracts import HydraulicSurfaceClass
from floodguard.urban_gis.reference import reference_package


def test_reference_exercises_all_surface_classes_and_one_roof_rule() -> None:
    package = reference_package()
    classes = {feature.surface_class for feature in package.hydraulic_features}
    assert classes == set(HydraulicSurfaceClass)
    assert len(package.roof_runoff_rules) == 1
    assert package.roof_runoff_rules[0].receiving_geometry is not None
    assert package.evidence_scope.value == "REFERENCE_FIXTURE"
