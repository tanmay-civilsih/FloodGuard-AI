from floodguard.reconstruction.calibration import load_calibrations
from floodguard.reconstruction.georeference import fit_affine


def test_real_ward_7_calibration_is_hash_pinned_and_within_gate() -> None:
    calibrations = load_calibrations()
    assert len(calibrations) == 1
    calibration = calibrations[0]
    assert calibration.ward_id == "7"
    assert calibration.source_sha256 == (
        "54f6a133d6978a692eef902ed7727d561b61af1080b4aa1fbc5547f2b80417b4"
    )
    fit = fit_affine(calibration, working_crs="EPSG:32645")
    assert fit.rmse_m < calibration.max_georeference_rmse_m
    assert fit.max_error_m < calibration.max_georeference_rmse_m

