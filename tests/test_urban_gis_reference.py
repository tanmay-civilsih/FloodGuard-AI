from floodguard.urban_gis.contracts import HydraulicSurfaceClass
from floodguard.urban_gis.reference import reference_package
from floodguard.urban_gis.service import package_bytes, sha256


def test_reference_exercises_all_surface_classes_and_one_roof_rule() -> None:
    package = reference_package()
    classes = {feature.surface_class for feature in package.hydraulic_features}
    assert classes == set(HydraulicSurfaceClass)
    assert len(package.roof_runoff_rules) == 1
    assert package.roof_runoff_rules[0].receiving_geometry is not None
    assert package.evidence_scope.value == "REFERENCE_FIXTURE"


def test_reference_identity_preserves_the_published_candidate() -> None:
    assert sha256(package_bytes(reference_package())) == (
        "03b2390c74c767bc37007b28ec791381b4dfae05be4e5042a6cbde86e556801a"
    )
