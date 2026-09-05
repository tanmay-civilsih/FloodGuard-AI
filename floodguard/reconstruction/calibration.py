"""Load versioned, source-hash-pinned reconstruction calibrations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from floodguard.reconstruction.contracts import ReconstructionCalibration

CALIBRATION_DIRECTORY = Path(__file__).with_name("calibrations")


def load_calibrations() -> list[ReconstructionCalibration]:
    calibrations: list[ReconstructionCalibration] = []
    for path in sorted(CALIBRATION_DIRECTORY.glob("*.json")):
        payload = cast(object, json.loads(path.read_text(encoding="utf-8")))
        calibrations.append(ReconstructionCalibration.model_validate(payload))
    return calibrations


def calibration_for_object(
    *,
    filename: str,
    sha256: str,
) -> ReconstructionCalibration:
    filename_matches: list[ReconstructionCalibration] = []
    for calibration in load_calibrations():
        if calibration.source_filename != filename:
            continue
        filename_matches.append(calibration)
        if calibration.source_sha256 == sha256:
            return calibration
    if filename_matches:
        raise LookupError(
            f"calibration exists for {filename}, but the immutable source SHA-256 changed"
        )
    raise LookupError(f"no reconstruction calibration exists for {filename}")
